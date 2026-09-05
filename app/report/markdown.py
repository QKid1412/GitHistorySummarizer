"""Renders a Portfolio as Markdown, for pasting into a CV draft or an issue."""

from __future__ import annotations

from datetime import date

from app.analysis.portfolio import Portfolio
from app.gitlog.collect import CLIENT, RELEASE, classify_branch
from app.gitlog.models import BACKEND, FRONTEND

_KIND_LABEL = {BACKEND: "Backend", FRONTEND: "Frontend", "unknown": "Other"}


def render(portfolio: Portfolio, title: str, generated: date | None = None) -> str:
    stamp = generated or date.today()
    lines: list[str] = [f"# {title}", ""]

    if portfolio.first and portfolio.last:
        lines += [f"{portfolio.first.isoformat()} to {portfolio.last.isoformat()} "
                  f"({portfolio.span_years:.1f} years)", ""]

    lines += ["## Totals", ""]
    lines += [
        f"- Commits authored: **{portfolio.commits:,}**",
        f"- Off-trunk commits: **{portfolio.offtrunk_commits:,}**",
        f"- Pull requests: **{portfolio.pull_requests:,}**",
        f"- Releases cut: **{portfolio.release_cuts:,}**",
        f"- Distinct files: **{portfolio.distinct_files:,}**",
        f"- Lines added / removed: **{portfolio.insertions:,}** / **{portfolio.deletions:,}**",
        "",
    ]

    for label, rank, total in portfolio.ranks():
        if rank:
            lines.append(f"- `{label}`: ranked **{rank}** of {total} trunk contributors")
    lines.append("")

    if len(portfolio.kinds) > 1:
        lines += ["## Split", "", "| Measure | " + " | ".join(_KIND_LABEL.get(k, k) for k in portfolio.kinds) + " |",
                  "|---|" + "---|" * len(portfolio.kinds)]
        for prop in portfolio.proportions:
            if not prop.total:
                continue
            cells = " | ".join(f"{prop.share(k) * 100:.1f}%" for k in portfolio.kinds)
            lines.append(f"| {prop.label} | {cells} |")
        lines.append("")

    if portfolio.years:
        lines += ["## Year by year", "", "| Year | Commits |" + (
            "".join(f" {_KIND_LABEL.get(k, k)} |" for k in portfolio.kinds) if len(portfolio.kinds) > 1 else ""),
            "|---|---|" + ("---|" * len(portfolio.kinds) if len(portfolio.kinds) > 1 else "")]
        for slice_ in portfolio.years:
            row = f"| {slice_.year} | {slice_.total} |"
            if len(portfolio.kinds) > 1:
                row += "".join(f" {slice_.share(k) * 100:.0f}% |" for k in portfolio.kinds)
            lines.append(row)
        lines.append("")

    owned = [b for b in portfolio.branches if b.mine > 0]
    if owned:
        lines += ["## Branch ownership", "", "| Branch | Yours | Total | Share | Type |", "|---|---|---|---|---|"]
        for branch in owned[:24]:
            kind = {RELEASE: "Release line", CLIENT: "Client"}.get(branch.kind or classify_branch(branch.name), "Other")
            short = branch.name[7:] if branch.name.startswith("origin/") else branch.name
            lines.append(f"| `{short}` | {branch.mine} | {branch.total} | {branch.share * 100:.0f}% | {kind} |")
        lines.append("")

    if portfolio.modules:
        lines += ["## Most-touched areas", ""]
        lines += [f"- `{name}` — {count} touches" for name, count in portfolio.modules[:15]]
        lines.append("")

    if portfolio.tickets:
        lines += ["## Project prefixes", ""]
        lines += [f"- `{name}` — {count} commits" for name, count in portfolio.tickets[:12]]
        lines.append("")

    mine, team = portfolio.test_ratio()
    if portfolio.total_touches_available():
        lines += ["## Testing", "",
                  f"- Test-path touches: **{mine * 100:.1f}%** of your changed paths"
                  + (f" (team-wide: {team * 100:.1f}%)" if team else ""),
                  "", "Path names only. This measures whether test files were edited, not coverage.", ""]

    lines += [
        "## Work streams", "",
        "_Write this section yourself._ This tool reads commit metadata, not code. It can show where",
        "you worked and how much, but not what a subsystem does or why it was hard. For each area",
        "above worth including, write two or three sentences: what it does, what you built, and the",
        "constraint that made it non-trivial.", "",
        "## Method", "",
        "Compiled from local git history only. No remote was contacted and no language model saw any",
        "code or commit content. Commits are non-merge commits matching "
        + ", ".join(f"`{s}`" for s in portfolio.subject)
        + ", de-duplicated by hash across trunk and every other branch.", "",
        "Repository names, branch names and ticket prefixes may be employer-internal. Review before sharing.", "",
        f"Generated {stamp.isoformat()}.",
    ]
    return "\n".join(lines) + "\n"
