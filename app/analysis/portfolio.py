"""Aggregates collected git history into the figures a portfolio report needs."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from app.gitlog.collect import CLIENT, OTHER, RELEASE, classify_branch, is_release_cut
from app.gitlog.models import BACKEND, FRONTEND, BranchStat, RepoReport

_PR = re.compile(r"\(#(\d+)\)")
_TICKET = re.compile(r"\b([A-Z][A-Z0-9]{1,14})-\d+\b")
_NOISE = {"src", "app", "lib", "source"}


@dataclass
class YearSlice:
    year: int
    total: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def share(self, kind: str) -> float:
        return (self.by_kind.get(kind, 0) / self.total) if self.total else 0.0


@dataclass
class Proportion:
    label: str
    by_kind: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.by_kind.values())

    def share(self, kind: str) -> float:
        return (self.by_kind.get(kind, 0) / self.total) if self.total else 0.0


@dataclass
class Portfolio:
    """Everything the renderers need, already reduced to numbers."""

    repos: list[RepoReport]
    subject: list[str]

    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    distinct_files: int = 0
    pull_requests: int = 0
    release_cuts: int = 0
    offtrunk_commits: int = 0
    first: date | None = None
    last: date | None = None

    years: list[YearSlice] = field(default_factory=list)
    proportions: list[Proportion] = field(default_factory=list)
    branches: list[BranchStat] = field(default_factory=list)
    client_branches: int = 0
    tickets: list[tuple[str, int]] = field(default_factory=list)
    modules: list[tuple[str, int]] = field(default_factory=list)

    @property
    def span_years(self) -> float:
        if not (self.first and self.last):
            return 0.0
        return (self.last - self.first).days / 365.25

    @property
    def kinds(self) -> list[str]:
        seen = [r.kind for r in self.repos]
        return [k for k in (BACKEND, FRONTEND) if k in seen] or sorted(set(seen))

    def total_touches_available(self) -> bool:
        return any(r.total_touches for r in self.repos)

    def test_ratio(self) -> tuple[float, float]:
        """(subject ratio, team ratio) of test-path touches across all repos."""
        mine_t = sum(r.test_touches for r in self.repos)
        mine_a = sum(r.total_touches for r in self.repos)
        team_t = sum(r.team_test_touches for r in self.repos)
        team_a = sum(r.team_total_touches for r in self.repos)
        return (mine_t / mine_a if mine_a else 0.0, team_t / team_a if team_a else 0.0)

    def ranks(self) -> list[tuple[str, int | None, int]]:
        return [(r.label, r.rank, len(r.contributors)) for r in self.repos]


def build(repos: list[RepoReport], subject: list[str]) -> Portfolio:
    portfolio = Portfolio(repos=repos, subject=subject)

    all_commits = [c for repo in repos for c in repo.commits]
    kind_of = {repo.label: repo.kind for repo in repos}

    portfolio.commits = len(all_commits)
    portfolio.insertions = sum(c.insertions for c in all_commits)
    portfolio.deletions = sum(c.deletions for c in all_commits)
    portfolio.distinct_files = sum(repo.distinct_files for repo in repos)
    portfolio.offtrunk_commits = sum(repo.offtrunk_commits for repo in repos)
    portfolio.release_cuts = sum(1 for c in all_commits if is_release_cut(c.subject))

    prs: set[tuple[str, str]] = set()
    for commit in all_commits:
        for number in _PR.findall(commit.subject):
            prs.add((commit.repo, number))
    portfolio.pull_requests = len(prs)

    if all_commits:
        portfolio.first = min(c.date for c in all_commits)
        portfolio.last = max(c.date for c in all_commits)

    portfolio.years = _years(all_commits, kind_of)
    portfolio.proportions = _proportions(repos, prs, kind_of)
    portfolio.branches = _branches(repos)
    portfolio.client_branches = len({b.name for b in portfolio.branches if (b.kind or classify_branch(b.name)) == CLIENT})
    portfolio.tickets = _tickets(all_commits)
    portfolio.modules = _modules(all_commits)
    return portfolio


# ----- reductions ---------------------------------------------------


def _years(commits, kind_of: dict[str, str]) -> list[YearSlice]:
    slices: dict[int, YearSlice] = {}
    for commit in commits:
        entry = slices.setdefault(commit.year, YearSlice(year=commit.year))
        entry.total += 1
        kind = kind_of.get(commit.repo, "unknown")
        entry.by_kind[kind] = entry.by_kind.get(kind, 0) + 1
    return [slices[y] for y in sorted(slices)]


def _proportions(repos: list[RepoReport], prs: set[tuple[str, str]], kind_of: dict[str, str]) -> list[Proportion]:
    def by_kind(fn) -> dict[str, int]:
        out: dict[str, int] = {}
        for repo in repos:
            out[repo.kind] = out.get(repo.kind, 0) + fn(repo)
        return out

    pr_counts: dict[str, int] = {}
    for repo_label, _ in prs:
        kind = kind_of.get(repo_label, "unknown")
        pr_counts[kind] = pr_counts.get(kind, 0) + 1

    return [
        Proportion("Commits", by_kind(lambda r: len(r.commits))),
        Proportion("Lines added", by_kind(lambda r: r.insertions)),
        Proportion("Lines removed", by_kind(lambda r: r.deletions)),
        Proportion("Files", by_kind(lambda r: r.distinct_files)),
        Proportion("Pull requests", pr_counts),
    ]


# How many branches of each type earn a place in the report, and the smallest
# contribution worth a row. Release snapshots and long-lived forks otherwise
# crowd out the client branches, which are usually the interesting ones.
_TYPE_CAPS = {RELEASE: 8, CLIENT: 12, OTHER: 5}
_MIN_COMMITS = 3


def _branches(repos: list[RepoReport]) -> list[BranchStat]:
    """Merges same-named branches across repositories, then balances by branch type."""
    merged: dict[str, BranchStat] = {}
    for repo in repos:
        for branch in repo.branches:
            existing = merged.get(branch.name)
            if existing is None:
                merged[branch.name] = BranchStat(
                    repo=repo.label, name=branch.name, mine=branch.mine,
                    total=branch.total, first=branch.first, last=branch.last,
                    kind=branch.kind or classify_branch(branch.name),
                )
                continue
            firsts = [d for d in (existing.first, branch.first) if d]
            lasts = [d for d in (existing.last, branch.last) if d]
            merged[branch.name] = BranchStat(
                repo=f"{existing.repo}+{repo.label}",
                name=branch.name,
                mine=existing.mine + branch.mine,
                total=existing.total + branch.total,
                first=min(firsts) if firsts else None,
                last=max(lasts) if lasts else None,
                kind=existing.kind or branch.kind or classify_branch(branch.name),
            )
    rows = [b for b in merged.values() if b.mine >= _MIN_COMMITS]
    rows.sort(key=lambda b: (_branch_priority(b), -b.share, -b.mine))

    kept: list[BranchStat] = []
    used: Counter[str] = Counter()
    for branch in rows:
        kind = branch.kind or classify_branch(branch.name)
        cap = _TYPE_CAPS.get(kind, _TYPE_CAPS[OTHER])
        if used[kind] < cap:
            used[kind] += 1
            kept.append(branch)
    return kept


def _branch_priority(branch: BranchStat) -> int:
    kind = branch.kind or classify_branch(branch.name)
    return {RELEASE: 0, CLIENT: 1}.get(kind, 2)


def _tickets(commits, limit: int = 12) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for commit in commits:
        for prefix in set(_TICKET.findall(commit.subject.upper())):
            counter[prefix] += 1
    return counter.most_common(limit)


def _modules(commits, limit: int = 20, depth: int = 2) -> list[tuple[str, int]]:
    """Most-touched directories, skipping generic top-level wrappers."""
    counter: Counter[str] = Counter()
    for commit in commits:
        for path in commit.paths:
            parts = [p for p in path.split("/")[:-1] if p]
            if not parts:
                continue
            while parts and parts[0].lower() in _NOISE and len(parts) > 1:
                parts = parts[1:]
            counter["/".join(parts[:depth])] += 1
    return counter.most_common(limit)
