"""Builds the drafting guide that accompanies the shareable report.

The shareable report keeps every number and removes every name. That leaves the
author with a scaffold and a job: say what the work actually was. This module
turns the measured figures into specific, answerable prompts rather than generic
advice, and drafts CV bullets with the real numbers already filled in.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.portfolio import Portfolio
from app.gitlog.collect import CLIENT, RELEASE, classify_branch
from app.gitlog.models import BACKEND, FRONTEND


@dataclass(frozen=True)
class Prompt:
    heading: str
    ask: str
    evidence: str = ""


@dataclass(frozen=True)
class Guide:
    intro: str
    placeholders: list[str]
    prompts: list[Prompt]
    bullets: list[str]
    checks: list[str]


def build(portfolio: Portfolio, redacted_names: list[str]) -> Guide:
    return Guide(
        intro=_intro(portfolio),
        placeholders=_placeholders(redacted_names),
        prompts=_prompts(portfolio),
        bullets=_bullets(portfolio),
        checks=_checks(),
    )


# ----- sections -----------------------------------------------------


def _intro(portfolio: Portfolio) -> str:
    years = f"{portfolio.span_years:.0f}" if portfolio.span_years >= 1 else "under a"
    return (
        f"Every figure on this page is measured from your git history and is safe to keep. "
        f"The names are not: branch names, ticket prefixes and directory paths have been replaced "
        f"with placeholders. Your job is to swap those for descriptions that carry the professional "
        f"signal without naming a customer, and to write the parts a commit log cannot supply — "
        f"what each system did, and what made it hard. There are {years} years of work here; "
        f"expect this to take an hour, not five minutes."
    )


def _placeholders(names: list[str]) -> list[str]:
    guidance = [
        "Replace each placeholder with a description, not a name. "
        "“a national logistics operator” tells a reader more than “Client A” "
        "and still names nobody.",
        "Say what kind of thing it was and what scale: “a national canal authority”, "
        "“a ferry operator’s scheduling integration”, “a container terminal deployment”.",
        "Directory placeholders become subsystem names in plain language — "
        "“the movement planning board” rather than the folder it lives in.",
        "Ticket prefixes usually need no replacement at all. Delete the section unless "
        "the split between projects is genuinely part of your story.",
    ]
    if names:
        preview = ", ".join(names[:4])
        guidance.insert(0, f"The placeholders on this page are: {preview}"
                           f"{' and others' if len(names) > 4 else ''}. "
                           "The local key file lists what each one stands for.")
    return guidance


def _prompts(portfolio: Portfolio) -> list[Prompt]:
    prompts: list[Prompt] = []

    for name, touches in portfolio.modules[:6]:
        prompts.append(Prompt(
            heading=name,
            ask="What does this subsystem do, what did you specifically build in it, and what "
                "constraint made it non-trivial? Three sentences. If you cannot name the hard part, "
                "it probably does not belong in the report.",
            evidence=f"{touches} file touches — one of your highest-volume areas",
        ))

    owned = [b for b in portfolio.branches if b.share >= 0.25 and b.mine >= 5]
    if owned:
        best = max(owned, key=lambda b: b.share)
        prompts.append(Prompt(
            heading="The branch you carried",
            ask="You wrote most of this branch. What was it for, why were you the one on it, and "
                "what would have gone wrong if it had been handled badly? Ownership of a whole line "
                "of work is the strongest thing a commit graph can show — say what it was.",
            evidence=f"{best.mine} of {best.total} commits ({best.share * 100:.0f}%)",
        ))

    if portfolio.release_cuts >= 5:
        prompts.append(Prompt(
            heading="Release responsibility",
            ask="You cut releases. Say what that involved at your organisation — who decided "
                "what shipped, what you checked before tagging, and whether you handled the "
                "aftermath when something went wrong. Readers do not assume this from a number.",
            evidence=f"{portfolio.release_cuts} version-bump commits",
        ))

    if len(portfolio.kinds) > 1 and portfolio.years:
        first, last = portfolio.years[0], portfolio.years[-1]
        moved = abs(last.share(BACKEND) - first.share(BACKEND)) > 0.2
        if moved:
            prompts.append(Prompt(
                heading="How your scope changed",
                ask="Your backend and frontend split shifted materially over this period. Was that "
                    "deliberate, and what did you have to learn to make it happen? A widening scope "
                    "is a promotion argument; an accidental drift is not.",
                evidence=f"Backend share moved from {first.share(BACKEND) * 100:.0f}% "
                         f"to {last.share(BACKEND) * 100:.0f}%",
            ))

    mine, team = portfolio.test_ratio()
    if portfolio.total_touches_available() and mine < 0.05:
        prompts.append(Prompt(
            heading="Testing",
            ask="Test files are a small share of what you touched. Decide now how you answer this "
                "in an interview: was it team convention, was coverage handled elsewhere, or is it "
                "a genuine gap you would fix? Any honest answer beats being surprised by the question.",
            evidence=f"{mine * 100:.1f}% of your changed paths were tests"
                     + (f", against {team * 100:.1f}% team-wide" if team else ""),
        ))

    prompts.append(Prompt(
        heading="What is missing entirely",
        ask="Code review, mentoring, incident response and design work leave no trace in authored "
            "commits. If you did those, add them here from memory — they are usually what "
            "separates one level from the next, and nothing in this report can find them for you.",
    ))
    return prompts


def _bullets(portfolio: Portfolio) -> list[str]:
    """CV bullets with the real numbers already in place and names left blank."""
    bullets: list[str] = []
    years = f"{portfolio.span_years:.0f}" if portfolio.span_years >= 1 else ""

    kinds = [k for k in portfolio.kinds if k in (BACKEND, FRONTEND)]
    stack = " and ".join({BACKEND: "backend", FRONTEND: "frontend"}[k] for k in kinds) or "full-stack"
    bullets.append(
        f"[Role] on [what the product does] — {stack} across "
        f"[technologies]{f', over {years} years' if years else ''}, "
        f"authoring {portfolio.commits:,} commits across {len(portfolio.repos)} "
        f"{'repository' if len(portfolio.repos) == 1 else 'repositories'}."
    )

    owned = [b for b in portfolio.branches if b.share >= 0.5 and b.mine >= 5]
    if owned:
        best = max(owned, key=lambda b: b.mine * b.share)
        bullets.append(
            f"Carried [what this branch was for] largely single-handed, authoring "
            f"{best.mine} of its {best.total} commits ({best.share * 100:.0f}%)."
        )

    if portfolio.release_cuts >= 5:
        bullets.append(f"Owned release cutting for [which product], tagging {portfolio.release_cuts} releases.")

    if portfolio.offtrunk_commits >= 50:
        bullets.append(
            f"Delivered [what kind of work] across [how many] long-lived deployment branches, "
            f"{portfolio.offtrunk_commits:,} commits of which never merged to trunk."
        )

    if portfolio.modules:
        bullets.append(f"Built and owned [subsystem] — [what it does and the hard constraint].")

    if portfolio.insertions:
        bullets.append(
            f"[Verb] [system] with [technology], contributing {portfolio.insertions:,} lines "
            f"across {portfolio.distinct_files:,} files."
        )
    return bullets


def _checks() -> list[str]:
    return [
        "Read every placeholder replacement back as if you were a competitor of your employer. "
        "If it identifies the customer, go more general.",
        "Delete the local key file, or keep it somewhere the report is never stored.",
        "Numbers are safe to publish, but check none of your replacements smuggle a name back in "
        "— a subsystem called after a client is still a client name.",
        "Domain terminology can identify an employer on its own. If your industry has few players, "
        "describe the problem class rather than the jargon.",
        "If your contract or handbook restricts describing client work, check it before publishing. "
        "This tool cannot know your obligations.",
    ]
