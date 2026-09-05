"""Collects one subject author's history from one or more local repositories."""

from __future__ import annotations

import re
from datetime import date

from app.gitlog.models import BranchStat, Commit, Contributor, RepoReport
from app.gitlog.repo import FIELD, GitRepo

CLIENT = "client"
RELEASE = "release"
OTHER = "other"

_RELEASE_NAME = re.compile(r"(^|/)(release|rel)([-_./]|$)", re.IGNORECASE)
_CLIENT_NAME = re.compile(r"(^|/)client([-_./]|$)", re.IGNORECASE)
_RELEASE_SUBJECT = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?(?:db\s+|database\s+)?version[\s_v]*\d", re.IGNORECASE)


def author_pattern(patterns: list[str]) -> str:
    """Builds one case-insensitive alternation regex matching any supplied identity."""
    cleaned = [re.escape(p.strip()) for p in patterns if p.strip()]
    if not cleaned:
        raise ValueError("At least one --author value is required.")
    return "(" + "|".join(cleaned) + ")"


def classify_branch(name: str) -> str:
    short = name.split("/", 1)[1] if name.startswith("origin/") else name
    if _CLIENT_NAME.search(short):
        return CLIENT
    if _RELEASE_NAME.search(short):
        return RELEASE
    return OTHER


def is_release_cut(subject: str) -> bool:
    """True for commits that only bump a version, e.g. `version 9.8.17`."""
    return bool(_RELEASE_SUBJECT.match(subject))


def collect_repo(
    repo: GitRepo,
    patterns: list[str],
    trunk: str | None = None,
    include_branches: bool = True,
    remote: bool = True,
    max_branches: int = 25,
) -> RepoReport:
    """Gathers trunk history, off-trunk branch attribution and contributor ranking."""
    pattern = author_pattern(patterns)
    trunk_ref = repo.trunk(trunk)

    report = RepoReport(label=repo.label, path=repo.path, kind=repo.kind, trunk=trunk_ref)
    report.identities = repo.identities()

    report.commits = repo.commits(trunk_ref, author_pattern=pattern, with_stats=True)
    report.trunk_commits = len(report.commits)

    report.test_touches, report.total_touches = repo.path_touches(trunk_ref, author_pattern=pattern)
    report.team_test_touches, report.team_total_touches = repo.path_touches(trunk_ref)

    report.contributors = _rank_contributors(repo, trunk_ref, patterns)

    if include_branches:
        scope = "--remotes" if remote else "--branches"
        report.offtrunk_commits = len(repo.shas([scope], author_pattern=pattern, exclude=trunk_ref))
        report.commits.extend(_offtrunk_commits(repo, trunk_ref, pattern, remote))
        report.branches = _branch_stats(repo, trunk_ref, pattern, patterns, remote, max_branches)

    return report


# ----- internals ----------------------------------------------------


def _candidates(repo: GitRepo, trunk_ref: str, pattern: str, remote: bool) -> list[str]:
    """Branches worth measuring exactly, most interesting first.

    Every branch is a candidate. `git log --source` is used only to order the
    ordinary feature branches, because it cannot be trusted to find the
    interesting ones: a branch whose commits are all reachable from some earlier
    ref is reported zero times, which is exactly what happens to a long-lived
    client branch sitting behind a release snapshot.
    """
    scope = "--remotes" if remote else "--branches"
    args = ["log", scope, "--not", trunk_ref, "--source", "--no-merges", "--format=%S",
            "--regexp-ignore-case", "--extended-regexp", f"--author={pattern}"]

    hint: dict[str, int] = {}
    for line in repo._run_quiet(*args).splitlines():
        ref = line.strip()
        if ref:
            hint[ref] = hint.get(ref, 0) + 1

    names = [n for n in repo.branches(include_remote=remote) if n != trunk_ref]
    priority = {RELEASE: 0, CLIENT: 1}
    names.sort(key=lambda n: (priority.get(classify_branch(n), 2), -hint.get(n, 0), n))
    return names


def _branch_stats(
    repo: GitRepo,
    trunk_ref: str,
    pattern: str,
    patterns: list[str],
    remote: bool,
    limit: int,
) -> list[BranchStat]:
    """Exact per-branch counts for the branches the fast pass flagged.

    Each branch costs one `git log`, from which both the subject's count and the
    branch total are derived, so a commit shared by several branches is counted
    honestly against each of them.
    """
    lowered = [p.strip().lower() for p in patterns if p.strip()]
    stats: list[BranchStat] = []
    budget = limit

    for name in _candidates(repo, trunk_ref, pattern, remote):
        # Release and client lines are always measured: there are few of them and
        # they carry the work that never reaches trunk. The cap exists to stop
        # hundreds of ordinary feature branches costing a git call each.
        if classify_branch(name) not in (RELEASE, CLIENT):
            if budget <= 0:
                continue
            budget -= 1
        mine_dates: list[date] = []
        total = 0
        args = ["log", name, "--not", trunk_ref, "--no-merges", "--date=short",
                f"--format=%an{FIELD}%ae{FIELD}%ad"]
        for line in repo._run_quiet(*args).splitlines():
            fields = line.split(FIELD)
            if len(fields) != 3:
                continue
            author = f"{fields[0]} <{fields[1]}>".lower()
            total += 1
            if any(p in author for p in lowered):
                try:
                    mine_dates.append(date.fromisoformat(fields[2].strip()))
                except ValueError:
                    mine_dates.append(date.min)
        if mine_dates:
            real = [d for d in mine_dates if d != date.min]
            stats.append(
                BranchStat(
                    repo="",
                    name=name,
                    mine=len(mine_dates),
                    total=total,
                    first=min(real) if real else None,
                    last=max(real) if real else None,
                    kind=classify_branch(name),
                )
            )

    stats.sort(key=lambda s: (-s.share, -s.mine))
    return stats


def _offtrunk_commits(repo: GitRepo, trunk_ref: str, pattern: str, remote: bool) -> list[Commit]:
    scope = "--remotes" if remote else "--branches"
    return repo.commits(scope, author_pattern=pattern, exclude=trunk_ref, with_stats=True)


def _rank_contributors(repo: GitRepo, trunk_ref: str, patterns: list[str]) -> list[Contributor]:
    """Ranks trunk contributors, folding the subject's identities into one row."""
    counts = repo.contributor_counts(trunk_ref)
    lowered = [p.strip().lower() for p in patterns if p.strip()]

    subject_total = 0
    others: dict[str, int] = {}
    for email, count in counts.items():
        if any(p in email for p in lowered):
            subject_total += count
        else:
            others[email] = others.get(email, 0) + count

    rows = [Contributor(key=email, commits=count) for email, count in others.items()]
    if subject_total:
        rows.append(Contributor(key="(subject)", commits=subject_total, is_subject=True))
    rows.sort(key=lambda c: c.commits, reverse=True)
    return rows
