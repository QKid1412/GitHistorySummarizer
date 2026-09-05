"""Validated local representations of GitHub API data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GitHubUser(BaseModel):
    login: str


class RepositoryInfo(BaseModel):
    full_name: str
    description: str | None = None
    language: str | None = None
    organization: str | None = None


class ChangedFile(BaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str | None = None
    timestamp: datetime | None = None


class ReviewInfo(BaseModel):
    reviewer: str | None = None
    state: str
    body: str | None = None
    submitted_at: datetime | None = None


class ReviewComment(BaseModel):
    reviewer: str | None = None
    body: str
    file: str | None = None
    line: int | None = None
    created_at: datetime | None = None


class PullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int
    title: str
    body: str | None = None
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    author: str | None = None
    labels: list[str] = Field(default_factory=list)
    milestone: str | None = None
    url: str
    additions: int = 0
    deletions: int = 0
    changed_files_count: int = 0
    commits_count: int = 0
    comments_count: int = 0
    review_comments_count: int = 0
    repository: RepositoryInfo | None = None
    files: list[ChangedFile] = Field(default_factory=list)
    commits: list[CommitInfo] = Field(default_factory=list)
    reviews: list[ReviewInfo] = Field(default_factory=list)
    review_comments: list[ReviewComment] = Field(default_factory=list)
    diff_is_partial: bool = False

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions

    @classmethod
    def from_api(cls, item: dict[str, Any], repository: RepositoryInfo | None = None) -> "PullRequest":
        return cls(
            number=item["number"], title=item["title"], body=item.get("body"), state=item["state"],
            created_at=item["created_at"], updated_at=item["updated_at"], closed_at=item.get("closed_at"),
            merged_at=item.get("merged_at"), author=(item.get("user") or {}).get("login"),
            labels=[label["name"] for label in item.get("labels", [])],
            milestone=(item.get("milestone") or {}).get("title"), url=item.get("html_url", ""),
            additions=item.get("additions", 0), deletions=item.get("deletions", 0),
            changed_files_count=item.get("changed_files", 0), commits_count=item.get("commits", 0),
            comments_count=item.get("comments", 0), review_comments_count=item.get("review_comments", 0),
            repository=repository,
        )
