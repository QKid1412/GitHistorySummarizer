"""A bounded JSON view of a Portfolio, safe to keep alongside the HTML report."""

from __future__ import annotations

from typing import Any

from app.analysis.portfolio import Portfolio
from app.gitlog.collect import classify_branch


def to_dict(portfolio: Portfolio) -> dict[str, Any]:
    """Summary figures only. Individual commits are deliberately not included."""
    mine, team = portfolio.test_ratio()
    return {
        "subject": portfolio.subject,
        "span": {
            "first": portfolio.first.isoformat() if portfolio.first else None,
            "last": portfolio.last.isoformat() if portfolio.last else None,
            "years": round(portfolio.span_years, 2),
        },
        "totals": {
            "commits": portfolio.commits,
            "offtrunk_commits": portfolio.offtrunk_commits,
            "pull_requests": portfolio.pull_requests,
            "release_cuts": portfolio.release_cuts,
            "distinct_files": portfolio.distinct_files,
            "insertions": portfolio.insertions,
            "deletions": portfolio.deletions,
        },
        "repositories": [
            {
                "label": repo.label,
                "path": str(repo.path),
                "kind": repo.kind,
                "trunk": repo.trunk,
                "trunk_commits": repo.trunk_commits,
                "offtrunk_commits": repo.offtrunk_commits,
                "insertions": repo.insertions,
                "deletions": repo.deletions,
                "distinct_files": repo.distinct_files,
                "rank": repo.rank,
                "contributors": len(repo.contributors),
                "test_touches": repo.test_touches,
                "total_touches": repo.total_touches,
            }
            for repo in portfolio.repos
        ],
        "proportions": [
            {"measure": p.label, "by_kind": p.by_kind, "shares": {k: round(p.share(k), 4) for k in p.by_kind}}
            for p in portfolio.proportions
        ],
        "years": [
            {"year": y.year, "commits": y.total, "by_kind": y.by_kind}
            for y in portfolio.years
        ],
        "branches": [
            {
                "name": b.name,
                "type": b.kind or classify_branch(b.name),
                "mine": b.mine,
                "total": b.total,
                "share": round(b.share, 4),
                "first": b.first.isoformat() if b.first else None,
                "last": b.last.isoformat() if b.last else None,
            }
            for b in portfolio.branches if b.mine
        ],
        "modules": [{"path": name, "touches": count} for name, count in portfolio.modules],
        "tickets": [{"prefix": name, "commits": count} for name, count in portfolio.tickets],
        "testing": {"subject_ratio": round(mine, 4), "team_ratio": round(team, 4)},
    }
