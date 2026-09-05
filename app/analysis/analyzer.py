"""Analysis orchestration, validation, and local analysis-result cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.analysis.models import CareerProfile, PRAnalysis, reject_unsupported_metrics
from app.analysis.prompts import CAREER_SYSTEM_PROMPT, PR_SYSTEM_PROMPT, career_user_prompt, pr_payload, pr_user_prompt
from app.github.models import PullRequest
from app.github.prs import prepared_diff
from app.llm.base import LLMClient


class CareerAnalyzer:
    def __init__(self, llm: LLMClient, cache_root: Path = Path("output/.cache/analysis")) -> None:
        self.llm = llm
        self.cache_root = cache_root

    def analyze_pr(self, pr: PullRequest, allow_raw_diff: bool, max_diff_chars: int, force: bool = False) -> PRAnalysis:
        diff, partial = prepared_diff(pr.files, max_diff_chars)
        key = hashlib.sha256((str(pr.updated_at) + str(allow_raw_diff) + str(max_diff_chars)).encode()).hexdigest()[:16]
        cache_path = self.cache_root / str(pr.number) / f"{key}.json"
        if not force and cache_path.exists():
            return PRAnalysis.model_validate_json(cache_path.read_text(encoding="utf-8"))
        analysis = self.llm.structured(system_prompt=PR_SYSTEM_PROMPT, user_prompt=pr_user_prompt(pr, allow_raw_diff, diff, partial), response_model=PRAnalysis)
        if analysis.pr_number != pr.number or analysis.title != pr.title:
            raise ValueError("LLM response does not match the requested PR.")
        facts = [pr.title, pr.body or "", *(commit.message for commit in pr.commits), *(comment.body for comment in pr.review_comments)]
        reject_unsupported_metrics(analysis, facts)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        return analysis

    def synthesize(self, analyses: list[PRAnalysis]) -> CareerProfile:
        return self.llm.structured(system_prompt=CAREER_SYSTEM_PROMPT, user_prompt=career_user_prompt([analysis.model_dump(mode="json") for analysis in analyses]), response_model=CareerProfile)
