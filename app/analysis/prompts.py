"""Conservative prompts and compact data serialization for the LLM boundary."""

from __future__ import annotations

import json
from typing import Any

from app.analysis.models import ENGINEERING_CATEGORIES
from app.github.models import PullRequest

PR_SYSTEM_PROMPT = """You are a senior engineering career analyst. Analyze a software engineer's real GitHub Pull Request and identify defensible evidence of engineering ability. You are NOT a generic PR summarizer.

Determine what the engineer actually contributed, technical problems solved, visible architecture decisions and trade-offs, senior-level behaviors, what can safely be claimed on a resume, and what cannot safely be claimed.

Be conservative. Never invent metrics, business impact, ownership, leadership, performance improvements, customer outcomes, or technologies not supported by the supplied evidence. Separate observable facts from reasonable inference. A resume bullet must be defensible from supplied GitHub evidence. Use only the allowed category values. An inference cannot be high confidence. Each score is a heuristic 0–20, and career_evidence_score must be their exact sum. Include five score explanations, one for every dimension. If evidence is missing, state that as an uncertainty rather than filling the gap.

Return only a JSON object matching the requested schema."""

CAREER_SYSTEM_PROMPT = """You are an expert Senior Software Engineer resume strategist. You are given structured evidence extracted from a software engineer's real GitHub history. Identify the strongest and most defensible evidence of engineering capability.

Do not exaggerate, invent metrics, infer business impact without evidence, or promote an inference into a fact. Prioritize ownership, architecture, technical complexity, difficult trade-offs, scalability, reliability, security, performance, cross-system impact, and business relevance only when supported. The final result must help write a truthful Senior Software Engineer resume and prepare for technical interviews. Return only JSON matching the requested schema."""


def pr_payload(pr: PullRequest, include_raw_diff: bool, diff: str, diff_is_partial: bool) -> dict[str, Any]:
    repository = pr.repository.model_dump() if pr.repository else None
    data: dict[str, Any] = {
        "repository": repository,
        "pr_metadata": {
            "number": pr.number, "title": pr.title, "body": pr.body, "state": pr.state,
            "created_at": str(pr.created_at), "updated_at": str(pr.updated_at), "closed_at": str(pr.closed_at),
            "merged_at": str(pr.merged_at), "author": pr.author, "labels": pr.labels,
            "milestone": pr.milestone, "url": pr.url, "additions": pr.additions, "deletions": pr.deletions,
            "total_changes": pr.total_changes, "changed_files": pr.changed_files_count,
        },
        "commits": [commit.model_dump(mode="json") for commit in pr.commits],
        "changed_files": [{"filename": file.filename, "status": file.status, "additions": file.additions, "deletions": file.deletions, "changes": file.changes, "patch_available": bool(file.patch)} for file in pr.files],
        "reviews": [review.model_dump(mode="json") for review in pr.reviews],
        "review_comments": [comment.model_dump(mode="json") for comment in pr.review_comments],
        "allowed_engineering_categories": ENGINEERING_CATEGORIES,
    }
    if include_raw_diff:
        data["raw_diff"] = {"content": diff, "is_partial": diff_is_partial, "notice": "This is a selected/truncated diff, not the entire repository."}
    else:
        data["raw_diff"] = {"sent": False, "notice": "Raw patches were intentionally withheld by local privacy configuration."}
    return data


def pr_user_prompt(pr: PullRequest, include_raw_diff: bool, diff: str, diff_is_partial: bool) -> str:
    return "Analyze this single PR. Return the PRAnalysis JSON object exactly.\n\n" + json.dumps(pr_payload(pr, include_raw_diff, diff, diff_is_partial), indent=2, default=str)


def career_user_prompt(analyses: list[dict[str, Any]]) -> str:
    return "Synthesize only the structured evidence below. Return the CareerProfile JSON object exactly.\n\n" + json.dumps({"pr_analyses": analyses}, indent=2)

