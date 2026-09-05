"""Turns a Portfolio into a shareable one by replacing employer-internal identifiers.

Every number survives redaction: commit counts, proportions, branch shares and
year totals are not sensitive. What gets replaced are the names that identify an
employer, a customer or an internal system — branch names, ticket prefixes,
directory paths and repository labels.

Placeholders are stable and ordered by prominence, so the redacted report stays
internally consistent: the branch called "Client deployment A" in the table is
the same one referred to anywhere else on the page.

The mapping itself is sensitive. It is never written into the shareable report;
`Redactor.legend()` returns it for a local-only file so the author knows what
each placeholder stands for.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.analysis.portfolio import Portfolio
from app.gitlog.collect import CLIENT, RELEASE, classify_branch
from app.gitlog.models import BACKEND, FRONTEND, BranchStat, RepoReport

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_KIND_REPO = {
    BACKEND: "Backend repository",
    FRONTEND: "Frontend repository",
    "unknown": "Repository",
}

_BRANCH_NOUN = {
    CLIENT: "Client deployment",
    RELEASE: "Release line",
    "other": "Feature branch",
}


def _name(noun: str, index: int) -> str:
    """A, B, ... Z, AA, AB, ... so the scheme never runs out."""
    if index < len(_LETTERS):
        return f"{noun} {_LETTERS[index]}"
    first, second = divmod(index, len(_LETTERS))
    return f"{noun} {_LETTERS[first - 1]}{_LETTERS[second]}"


class Redactor:
    """Builds and applies a stable real-name to placeholder mapping."""

    def __init__(self, portfolio: Portfolio) -> None:
        self.repos: dict[str, str] = {}
        self.branches: dict[str, str] = {}
        self.tickets: dict[str, str] = {}
        self.modules: dict[str, str] = {}
        self._build(portfolio)

    # ----- construction ---------------------------------------------

    def _build(self, portfolio: Portfolio) -> None:
        kinds: dict[str, int] = {}
        for repo in portfolio.repos:
            noun = _KIND_REPO.get(repo.kind, _KIND_REPO["unknown"])
            seen = kinds.get(noun, 0)
            kinds[noun] = seen + 1
            self.repos[repo.label] = noun if seen == 0 else f"{noun} {seen + 1}"

        counters: dict[str, int] = {}
        for branch in portfolio.branches:
            kind = classify_branch(branch.name)
            noun = _BRANCH_NOUN.get(kind, _BRANCH_NOUN["other"])
            index = counters.get(noun, 0)
            counters[noun] = index + 1
            self.branches[branch.name] = _name(noun, index)

        for index, (prefix, _) in enumerate(portfolio.tickets):
            self.tickets[prefix] = _name("Project", index).replace("Project ", "PROJ-")

        for index, (path, _) in enumerate(portfolio.modules):
            self.modules[path] = _name("Module", index)

    # ----- application ----------------------------------------------

    def apply(self, portfolio: Portfolio) -> Portfolio:
        repos = [
            replace(report, label=self.repos.get(report.label, report.label), commits=[])
            for report in portfolio.repos
        ]
        label_of = {old: new for old, new in self.repos.items()}

        branches = [
            replace(
                branch,
                name=self.branches.get(branch.name, branch.name),
                repo=label_of.get(branch.repo, branch.repo),
            )
            for branch in portfolio.branches
        ]

        return replace(
            portfolio,
            repos=repos,
            subject=["you"],
            branches=branches,
            tickets=[(self.tickets.get(p, p), n) for p, n in portfolio.tickets],
            modules=[(self.modules.get(p, p), n) for p, n in portfolio.modules],
        )

    def scrub(self, text: str) -> str:
        """Replaces any known identifier appearing in free text, longest name first."""
        if not text:
            return text
        pairs = sorted(
            [*self.repos.items(), *self.branches.items(), *self.tickets.items(), *self.modules.items()],
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for real, placeholder in pairs:
            if not real:
                continue
            short = real[len("origin/"):] if real.startswith("origin/") else real
            for needle in (real, short):
                text = re.sub(re.escape(needle), placeholder, text, flags=re.IGNORECASE)
        return text

    # ----- disclosure -----------------------------------------------

    def legend(self) -> list[tuple[str, str, str]]:
        """(category, placeholder, real name), for a local-only key file."""
        rows: list[tuple[str, str, str]] = []
        for real, placeholder in self.repos.items():
            rows.append(("Repository", placeholder, real))
        for real, placeholder in self.branches.items():
            rows.append(("Branch", placeholder, real))
        for real, placeholder in self.tickets.items():
            rows.append(("Ticket prefix", placeholder, real))
        for real, placeholder in self.modules.items():
            rows.append(("Directory", placeholder, real))
        return rows

    def legend_text(self) -> str:
        lines = [
            "REDACTION KEY - KEEP THIS FILE LOCAL",
            "",
            "Maps the placeholders in the shareable report back to the real names.",
            "Do not publish this file or paste its contents anywhere.",
            "",
        ]
        width = max((len(p) for _, p, _ in self.legend()), default=10)
        category = None
        for group, placeholder, real in self.legend():
            if group != category:
                category = group
                lines.append(f"\n{group}")
                lines.append("-" * len(group))
            lines.append(f"  {placeholder.ljust(width)}  ->  {real}")
        return "\n".join(lines) + "\n"


def apply_llm_terms(redactor: Redactor, suggestions: dict[str, str]) -> Redactor:
    """Overlays model-suggested generic descriptions onto the placeholder mapping.

    A rule-based placeholder says "Client deployment A". A good generic
    description says "a national logistics operator" — more useful on a CV and
    still not naming the customer. Suggestions are keyed by the real name.
    """
    for real, generic in suggestions.items():
        cleaned = generic.strip()
        if not cleaned:
            continue
        if real in redactor.branches:
            redactor.branches[real] = cleaned
        elif real in redactor.tickets:
            redactor.tickets[real] = cleaned
        elif real in redactor.modules:
            redactor.modules[real] = cleaned
        elif real in redactor.repos:
            redactor.repos[real] = cleaned
    return redactor
