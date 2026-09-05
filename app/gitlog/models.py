"""Value types describing local git history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BACKEND = "backend"
FRONTEND = "frontend"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Identity:
    """One author name/email pair seen in a repository."""

    name: str
    email: str
    commits: int

    @property
    def label(self) -> str:
        return f"{self.name} <{self.email}>"


@dataclass(frozen=True)
class Commit:
    """A single non-merge commit authored by the subject."""

    sha: str
    date: date
    author_name: str
    author_email: str
    subject: str
    repo: str
    files: int = 0
    insertions: int = 0
    deletions: int = 0
    paths: tuple[str, ...] = ()

    @property
    def year(self) -> int:
        return self.date.year


@dataclass(frozen=True)
class BranchStat:
    """How much of a branch's off-trunk work belongs to the subject."""

    repo: str
    name: str
    mine: int
    total: int
    first: date | None
    last: date | None
    # Classified from the real branch name at collection time. Kept on the record
    # so it survives redaction, which replaces the name with a placeholder.
    kind: str = ""

    @property
    def share(self) -> float:
        return (self.mine / self.total) if self.total else 0.0


@dataclass(frozen=True)
class Contributor:
    """A contributor's commit count on trunk, used for ranking."""

    key: str
    commits: int
    is_subject: bool = False


@dataclass
class RepoReport:
    """Everything collected from one repository."""

    label: str
    path: Path
    kind: str
    trunk: str
    commits: list[Commit] = field(default_factory=list)
    branches: list[BranchStat] = field(default_factory=list)
    contributors: list[Contributor] = field(default_factory=list)
    identities: list[Identity] = field(default_factory=list)
    trunk_commits: int = 0
    offtrunk_commits: int = 0
    test_touches: int = 0
    total_touches: int = 0
    team_test_touches: int = 0
    team_total_touches: int = 0

    @property
    def insertions(self) -> int:
        return sum(c.insertions for c in self.commits)

    @property
    def deletions(self) -> int:
        return sum(c.deletions for c in self.commits)

    @property
    def distinct_files(self) -> int:
        return len({p for c in self.commits for p in c.paths})

    @property
    def rank(self) -> int | None:
        """1-based position of the subject among trunk contributors."""
        for position, contributor in enumerate(self.contributors, 1):
            if contributor.is_subject:
                return position
        return None
