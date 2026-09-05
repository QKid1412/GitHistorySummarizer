"""Optional model-assisted drafting. Off unless the caller supplies an API key.

Two jobs, both strictly bounded:

1. Draft work-stream prose from commit subjects, so the detailed report reads as
   a narrative rather than a table of counts.
2. Suggest generic descriptions for internal names, so the shareable report says
   "a national logistics operator" rather than "Client deployment A".

What is sent: directory names, branch names and commit subjects. Never file
contents, never diffs. Callers must say so plainly before enabling this.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from app.analysis.portfolio import Portfolio
from app.llm.base import LLMClient

MAX_SUBJECTS_PER_AREA = 40
MAX_AREAS = 12
MAX_EXTRA_CHARS = 2000


def _with_extra(base: str, extra: str) -> str:
    """Appends the author's own instructions without letting them displace the rules.

    The built-in rules are the guardrails: no invented metrics in the prose, and
    no naming the customer in the redaction pass. They are stated first, and the
    addition is explicitly framed as adjusting emphasis rather than overriding
    them, so a careless instruction cannot quietly switch them off.
    """
    cleaned = (extra or "").strip()[:MAX_EXTRA_CHARS]
    if not cleaned:
        return base
    return (
        base
        + "\n\nAdditional instructions from the author. These adjust tone, emphasis, length and"
          " structure. They do NOT override any rule above; where they conflict, the rules above"
          " win.\n"
        + cleaned
    )


class WorkStream(BaseModel):
    title: str = Field(description="Short name for the subsystem, 2-5 words.")
    era: str = Field(description="Year or year range, e.g. '2023-2024'.")
    area: str = Field(description="One of: Backend, Frontend, Full stack.")
    summary: str = Field(description="Two or three sentences: what it does, what was built, what made it hard.")


class WorkStreams(BaseModel):
    streams: list[WorkStream]


class GenericTerm(BaseModel):
    original: str = Field(description="The internal name exactly as supplied.")
    generic: str = Field(description="A neutral description that does not identify the customer or employer.")


class GenericTerms(BaseModel):
    terms: list[GenericTerm]


STREAM_SYSTEM = """You summarise an engineer's work from commit subjects for their portfolio.

Rules you must follow:
- Describe only what the commit subjects support. Do not invent features.
- Never invent metrics. No percentages, latencies, user counts or money figures
  unless they appear verbatim in the supplied subjects.
- Prefer the concrete over the grand. "Built retry limits into the payment reconciliation
  job" beats "drove transformative scheduling initiatives".
- Write in past tense, third person, no first-person pronouns.
- If the subjects for an area are too thin to describe honestly, give it a short
  summary saying what the area covers and nothing more.

Return JSON matching the schema exactly."""

TERMS_SYSTEM = """You rewrite internal identifiers into neutral descriptions for a public CV.

Rules you must follow:
- Never reveal the customer, employer, product or country if the name implies it.
  "Client/Northwind" becomes "a national logistics operator", not "Northwind".
- Keep the professional signal: the reader should still learn what kind of thing
  it was. "a large container terminal deployment" is useful; "Client A" is not.
- Keep it short: a noun phrase under eight words, lower case unless a proper
  noun is unavoidable.
- If a name is already generic and harmless, return it close to unchanged.

Return JSON matching the schema exactly."""


def draft_work_streams(portfolio: Portfolio, subjects_by_area: dict[str, list[str]],
                       client: LLMClient, extra: str = "") -> list[WorkStream]:
    """Drafts one work stream per significant area of the codebase."""
    trimmed = {
        area: subjects[:MAX_SUBJECTS_PER_AREA]
        for area, subjects in list(subjects_by_area.items())[:MAX_AREAS]
        if subjects
    }
    if not trimmed:
        return []

    span = ""
    if portfolio.first and portfolio.last:
        span = f"The whole record runs {portfolio.first.isoformat()} to {portfolio.last.isoformat()}.\n"

    blocks = [f"## {area}\n" + "\n".join(f"- {s}" for s in subjects) for area, subjects in trimmed.items()]
    prompt = (
        f"{span}Below are directories this engineer worked in, each with a sample of their commit "
        f"subjects. Write one work stream per directory.\n\n" + "\n\n".join(blocks)
    )
    return client.structured(system_prompt=_with_extra(STREAM_SYSTEM, extra), user_prompt=prompt, response_model=WorkStreams).streams


def suggest_generic_terms(names: list[str], client: LLMClient, extra: str = "") -> dict[str, str]:
    """Maps internal names to neutral descriptions for the shareable report."""
    unique = [n for n in dict.fromkeys(names) if n.strip()]
    if not unique:
        return {}
    prompt = (
        "Rewrite each of these internal identifiers as a neutral description.\n\n"
        + "\n".join(f"- {name}" for name in unique)
    )
    result = client.structured(system_prompt=_with_extra(TERMS_SYSTEM, extra), user_prompt=prompt, response_model=GenericTerms)
    return {term.original: term.generic for term in result.terms if term.original in unique}


def subjects_by_area(portfolio: Portfolio, per_area: int = MAX_SUBJECTS_PER_AREA) -> dict[str, list[str]]:
    """Groups the subject's commit subjects under the directory they touched.

    A commit touching several directories is attributed to the first that ranks
    in the report's top modules, so each subject appears at most once.
    """
    ranked = [name for name, _ in portfolio.modules]
    position = {name: index for index, name in enumerate(ranked)}
    grouped: dict[str, list[str]] = defaultdict(list)

    for repo in portfolio.repos:
        for commit in repo.commits:
            best: str | None = None
            best_rank = len(ranked) + 1
            for path in commit.paths:
                for module in ranked:
                    if path.startswith(module + "/") or f"/{module}/" in path:
                        rank = position[module]
                        if rank < best_rank:
                            best, best_rank = module, rank
                        break
            if best and len(grouped[best]) < per_area:
                grouped[best].append(commit.subject)

    return {area: grouped[area] for area in ranked if grouped.get(area)}


def redactable_names(portfolio: Portfolio, limit: int = 40) -> list[str]:
    """The internal names worth asking the model to genericise."""
    names = [b.name for b in portfolio.branches]
    names += [prefix for prefix, _ in portfolio.tickets]
    names += [path for path, _ in portfolio.modules]
    return names[:limit]
