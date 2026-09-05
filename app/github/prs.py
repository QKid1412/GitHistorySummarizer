"""PR collection, local GitHub cache, deterministic selection, and diff sanitization."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Iterable

from app.github.client import GitHubClient, GitHubError
from app.github.models import ChangedFile, CommitInfo, PullRequest, RepositoryInfo, ReviewComment, ReviewInfo

GENERATED_PATTERNS = (
    re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml)$", re.I),
    re.compile(r"\.min\.(js|css)$", re.I),
    re.compile(r"(^|/)(generated|bin|obj|dist|build|coverage)(/|$)", re.I),
)
KEYWORDS = ("architecture", "refactor", "performance", "security", "cache", "distributed", "kafka", "azure", "database", "migration", "authentication", "authorization", "scaling", "optimization")


class PRService:
    def __init__(self, client: GitHubClient, cache_root: Path = Path("output/.cache")) -> None:
        self.client = client
        self.cache_root = cache_root

    def repository(self, repo: str) -> RepositoryInfo:
        data = self.client.get(f"/repos/{repo}")
        return RepositoryInfo(full_name=data["full_name"], description=data.get("description"), language=data.get("language"), organization=(data.get("organization") or {}).get("login"))

    def list_pull_requests(self, repo: str, author: str, start: date | None, end: date | None) -> list[PullRequest]:
        repository = self.repository(repo)
        items = self.client.get_list(f"/repos/{repo}/pulls", {"state": "all", "sort": "updated", "direction": "desc"})
        prs: list[PullRequest] = []
        for item in items:
            if (item.get("user") or {}).get("login", "").lower() != author.lower():
                continue
            created = date.fromisoformat(item["created_at"][:10])
            if start and created < start or end and created > end:
                continue
            prs.append(PullRequest.from_api(item, repository))
        return prs

    def fetch_details(self, repo: str, summary: PullRequest, include_reviews: bool, include_comments: bool, force: bool = False) -> PullRequest:
        cache_path = self._cache_path(repo, summary.number)
        if not force and cache_path.exists():
            cached = PullRequest.model_validate_json(cache_path.read_text(encoding="utf-8"))
            if cached.updated_at >= summary.updated_at:
                return cached
        detail = PullRequest.from_api(self.client.get(f"/repos/{repo}/pulls/{summary.number}"), summary.repository)
        files = [ChangedFile(filename=item["filename"], status=item["status"], additions=item.get("additions", 0), deletions=item.get("deletions", 0), changes=item.get("changes", 0), patch=item.get("patch")) for item in self.client.get_list(f"/repos/{repo}/pulls/{summary.number}/files")]
        commits = [CommitInfo(sha=item["sha"], message=(item.get("commit") or {}).get("message", ""), author=((item.get("author") or {}).get("login")), timestamp=(item.get("commit") or {}).get("author", {}).get("date")) for item in self.client.get_list(f"/repos/{repo}/pulls/{summary.number}/commits")]
        reviews: list[ReviewInfo] = []
        comments: list[ReviewComment] = []
        if include_reviews:
            reviews = [ReviewInfo(reviewer=(item.get("user") or {}).get("login"), state=item.get("state", "PENDING"), body=item.get("body"), submitted_at=item.get("submitted_at")) for item in self.client.get_list(f"/repos/{repo}/pulls/{summary.number}/reviews")]
        if include_comments:
            comments = [ReviewComment(reviewer=(item.get("user") or {}).get("login"), body=item.get("body", ""), file=item.get("path"), line=item.get("line") or item.get("original_line"), created_at=item.get("created_at")) for item in self.client.get_list(f"/repos/{repo}/pulls/{summary.number}/comments")]
        complete = detail.model_copy(update={"files": files, "commits": commits, "reviews": reviews, "review_comments": comments})
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(complete.model_dump_json(indent=2), encoding="utf-8")
        return complete

    def _cache_path(self, repo: str, number: int) -> Path:
        return self.cache_root / repo.replace("/", "__") / f"pr_{number}.json"


def rank_pr(pr: PullRequest) -> float:
    """Cheap, explainable triage score; it is not an assessment of code quality."""
    text = " ".join([pr.title, pr.body or "", *pr.labels]).lower()
    keyword_hits = sum(keyword in text for keyword in KEYWORDS)
    merged = 8 if pr.merged_at else 0
    size = min(12, (pr.changed_files_count * 0.7) + ((pr.additions + pr.deletions) / 250))
    collaboration = min(5, pr.comments_count + pr.review_comments_count + len(pr.reviews) + len(pr.review_comments) / 2)
    return merged + size + (keyword_hits * 3) + collaboration


def select_balanced(prs: Iterable[PullRequest], maximum: int) -> list[PullRequest]:
    """Use a transparent, approximate mix so PR size never becomes the only selection signal."""
    ordered = sorted(prs, key=rank_pr, reverse=True)
    selected: list[PullRequest] = []
    text = lambda pr: (pr.title + " " + (pr.body or "") + " " + " ".join(pr.labels)).lower()
    buckets = [
        (round(maximum * 0.40), lambda pr: pr.changed_files_count >= 8 or pr.total_changes >= 500),
        (round(maximum * 0.20), lambda pr: any(word in text(pr) for word in ("architecture", "refactor", "migration", "distributed", "cache", "kafka", "scal"))),
        (round(maximum * 0.15), lambda pr: any(word in text(pr) for word in ("performance", "security", "authentication", "authorization", "optimization"))),
        (round(maximum * 0.15), lambda pr: any(word in text(pr) for word in ("feature", "product", "customer", "enable"))),
        (max(1, round(maximum * 0.10)), lambda pr: pr.total_changes <= 100 and any(word in text(pr) for word in ("security", "performance", "bug", "fix", "auth"))),
    ]
    for target, predicate in buckets:
        added = 0
        for pr in ordered:
            if added >= target or len(selected) >= maximum:
                break
            if pr.number not in {candidate.number for candidate in selected} and predicate(pr):
                selected.append(pr)
                added += 1
    for pr in ordered:
        if len(selected) >= maximum:
            break
        if pr.number not in {candidate.number for candidate in selected}:
            selected.append(pr)
    return selected


def prepared_diff(files: list[ChangedFile], max_chars: int) -> tuple[str, bool]:
    """Create explicitly partial, source-first diff text; unavailable patches are retained as metadata."""
    prioritized = sorted(files, key=lambda file: (is_generated(file.filename), -file.changes, file.filename))
    chunks: list[str] = []
    used = 0
    partial = False
    for file in prioritized:
        if is_generated(file.filename):
            partial = True
            continue
        if not file.patch:
            chunks.append(f"\n--- {file.filename} (patch unavailable; {file.changes} changed lines)\n")
            partial = True
            continue
        chunk = f"\n--- {file.filename}\n{file.patch}\n"
        remaining = max_chars - used
        if remaining <= 0:
            partial = True
            break
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining] + "\n[DIFF TRUNCATED]\n")
            partial = True
            break
        chunks.append(chunk)
        used += len(chunk)
    return "".join(chunks), partial


def is_generated(filename: str) -> bool:
    return any(pattern.search(filename) for pattern in GENERATED_PATTERNS)
