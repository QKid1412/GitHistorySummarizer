"""Turns a Portfolio into the requested report versions on disk.

Shared by the CLI and the local UI so both produce identical output. Model
assistance is optional and degrades to the offline path on any failure: a broken
API key should cost you the prose, not the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.analysis.portfolio import Portfolio
from app.output.json_output import write_json
from app.report import guide as guide_module
from app.report import html, json_report, markdown, narrative, team_html
from app.report.html import DETAILED, SHAREABLE

TEAM = "team"
from app.report.redact import Redactor, apply_llm_terms

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


PROSE = "prose"
REDACTION = "redaction"


@dataclass
class JobConfig:
    """Provider settings for one model job. Blank fields inherit the shared ones.

    The two jobs have different needs. Redaction is short, structured, and sees
    the most sensitive names, so it suits a cheap or locally hosted model. Prose
    drafting is where a stronger model earns its cost.
    """

    api_key: str = ""
    model: str = ""
    base_url: str = ""
    instructions: str = ""

    def resolved(self, key: str, model: str, base_url: str) -> "JobConfig":
        return JobConfig(
            api_key=(self.api_key or key).strip(),
            model=(self.model or model).strip(),
            base_url=(self.base_url or base_url).strip(),
            instructions=self.instructions,
        )


@dataclass
class Options:
    title: str = "Contribution record"
    subtitle: str | None = None
    # Never defaulted from `title`/`subtitle`: free text you wrote for your own
    # copy may name the product or employer, and the identifier mapping cannot
    # catch a name it never saw in the git history.
    shareable_title: str | None = None
    shareable_subtitle: str | None = None
    # Shown as the report byline. Safe in both versions: your own name is not
    # employer-confidential, and a portfolio without it is anonymous.
    author_name: str | None = None
    team_title: str | None = None
    versions: tuple[str, ...] = (DETAILED, SHAREABLE)
    # Team report only. How many contributors to profile, most active first.
    top: int = 8
    use_ai: bool = False
    api_key: str = ""
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    # Optional per-job overrides. Left blank, both inherit the three above.
    prose: JobConfig = field(default_factory=JobConfig)
    redaction: JobConfig = field(default_factory=JobConfig)

    def job(self, name: str) -> JobConfig:
        source = self.prose if name == PROSE else self.redaction
        return source.resolved(self.api_key, self.model, self.base_url)


@dataclass
class Outputs:
    files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ai_used: bool = False


def generate(portfolio: Portfolio, out_dir: Path, options: Options, generated: date | None = None,
             repos: list | None = None) -> Outputs:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = Outputs()

    prose_client = redaction_client = None
    if options.use_ai:
        prose_client = _client(options, PROSE, outputs)
        # Only built when the shareable version needs it, and only reported once.
        if SHAREABLE in options.versions:
            redaction_client = _client(options, REDACTION, outputs)

    streams = _streams(portfolio, prose_client, options, outputs) if prose_client else None
    outputs.ai_used = bool(streams)

    if DETAILED in options.versions:
        _write_detailed(portfolio, out_dir, options, streams, outputs, generated)

    if SHAREABLE in options.versions:
        _write_shareable(portfolio, out_dir, options, redaction_client, streams, outputs, generated)

    if TEAM in options.versions:
        _write_team(out_dir, options, outputs, generated, repos)

    return outputs


# ----- versions -----------------------------------------------------


def _write_detailed(portfolio, out_dir: Path, options: Options, streams, outputs: Outputs, generated) -> None:
    folder = out_dir / "detailed"
    folder.mkdir(parents=True, exist_ok=True)

    page = html.render(
        portfolio, options.title, options.subtitle, generated,
        mode=DETAILED, streams=streams, ai_used=outputs.ai_used,
        author_name=options.author_name,
    )
    (folder / "report.html").write_text(page, encoding="utf-8")
    (folder / "report.md").write_text(markdown.render(portfolio, options.title, generated), encoding="utf-8")
    write_json(folder / "report.json", json_report.to_dict(portfolio))
    outputs.files += [folder / "report.html", folder / "report.md", folder / "report.json"]


def _write_shareable(portfolio, out_dir: Path, options: Options, client, streams, outputs: Outputs, generated) -> None:
    folder = out_dir / "shareable"
    folder.mkdir(parents=True, exist_ok=True)

    redactor = Redactor(portfolio)
    if client:
        _genericise(portfolio, redactor, client, options, outputs)

    redacted = redactor.apply(portfolio)
    placeholders = [redactor.branches.get(b.name, b.name) for b in portfolio.branches][:8]
    drafting = guide_module.build(redacted, placeholders)

    scrubbed = None
    if streams:
        scrubbed = [
            type(stream)(
                title=redactor.scrub(stream.title),
                era=stream.era,
                area=stream.area,
                summary=redactor.scrub(stream.summary),
            )
            for stream in streams
        ]

    title = redactor.scrub(options.shareable_title) if options.shareable_title else _generic_title(options.title)
    subtitle = redactor.scrub(options.shareable_subtitle) if options.shareable_subtitle else None

    page = html.render(
        redacted, title, subtitle, generated,
        mode=SHAREABLE, streams=scrubbed, guide=drafting, ai_used=outputs.ai_used,
        author_name=options.author_name,
    )
    (folder / "report.html").write_text(page, encoding="utf-8")
    (folder / "report.md").write_text(markdown.render(redacted, title, generated), encoding="utf-8")
    write_json(folder / "report.json", json_report.to_dict(redacted))

    # The key maps placeholders back to real names, so it is the one artefact here
    # that must never be shared. It sits outside the shareable folder deliberately.
    key = out_dir / "redaction-key.txt"
    key.write_text(redactor.legend_text(), encoding="utf-8")

    outputs.files += [folder / "report.html", folder / "report.md", folder / "report.json", key]


def _write_team(out_dir: Path, options: Options, outputs: Outputs, generated, repos) -> None:
    """The team report profiles every contributor, so it needs the repositories, not the portfolio."""
    if not repos:
        outputs.warnings.append("The team report needs repository access and none was supplied; skipped it.")
        return

    from datetime import date as _date, timedelta

    from app.analysis import team as team_module

    folder = out_dir / "team"
    folder.mkdir(parents=True, exist_ok=True)
    since = ((generated or _date.today()) - timedelta(days=365)).isoformat()

    try:
        people = team_module.profile_team(repos, top=options.top, since=since)
    except Exception as error:  # noqa: BLE001 - one bad repo must not lose the other reports
        outputs.warnings.append(f"The team report could not be built ({error}).")
        return

    if not people:
        outputs.warnings.append("No contributors were found, so no team report was written.")
        return

    pairs = team_module.rank(people)
    page = team_html.render(pairs, options.team_title or "Contributor record",
                            [r.label for r in repos], generated)
    (folder / "team-report.html").write_text(page, encoding="utf-8")
    write_json(folder / "team-report.json", _team_json(pairs))
    outputs.files += [folder / "team-report.html", folder / "team-report.json"]


def _team_json(pairs) -> dict:
    return {
        "contributors": [
            {
                "rank": index,
                "name": person.display,
                "emails": sorted(person.emails),
                "commits": person.commits,
                "by_kind": person.by_kind,
                "first": person.first,
                "last": person.last,
                "years": round(person.years, 2),
                "recent": person.recent,
                "merges_to_trunk": person.merges_to_trunk,
                "version_cuts": person.version_cuts,
                "test_ratio": round(person.test_ratio, 4),
                "codeowner": person.codeowner,
                "architecture": person.architecture,
                "branches": {k: {"mine": v[0], "total": v[1]} for k, v in person.branches.items()},
                "top_modules": [{"module": m, "touches": n} for m, n in person.modules.most_common(8)],
                "score": score.total,
                "components": [
                    {"key": c.key, "points": c.points, "max": c.maximum, "evidence": c.evidence}
                    for c in score.components
                ],
            }
            for index, (person, score) in enumerate(pairs, 1)
        ]
    }


# ----- model assistance ---------------------------------------------


def _client(options: Options, job: str, outputs: Outputs):
    """Builds the provider client for one job, or returns None and explains why."""
    config = options.job(job)
    if not config.api_key:
        outputs.warnings.append(
            f"AI drafting was requested for {job} but no API key was supplied; "
            "wrote the offline version instead."
        )
        return None
    try:
        from app.llm.openai_client import OpenAICompatibleClient
        return OpenAICompatibleClient(
            config.api_key,
            config.model or DEFAULT_MODEL,
            config.base_url or DEFAULT_BASE_URL,
        )
    except Exception as error:  # noqa: BLE001 - any provider failure falls back
        outputs.warnings.append(
            f"Could not start the AI client for {job} ({error}); wrote the offline version instead."
        )
        return None


def _streams(portfolio: Portfolio, client, options: Options, outputs: Outputs):
    try:
        by_area = narrative.subjects_by_area(portfolio)
        if not by_area:
            outputs.warnings.append("No commit subjects could be grouped by directory, so no prose was drafted.")
            return None
        return narrative.draft_work_streams(portfolio, by_area, client, options.job(PROSE).instructions)
    except Exception as error:  # noqa: BLE001
        outputs.warnings.append(f"AI drafting failed ({error}); the report keeps its drafting prompts instead.")
        return None


def _genericise(portfolio: Portfolio, redactor: Redactor, client, options: Options, outputs: Outputs) -> None:
    try:
        names = narrative.redactable_names(portfolio)
        suggestions = narrative.suggest_generic_terms(names, client, options.job(REDACTION).instructions)
        if suggestions:
            apply_llm_terms(redactor, suggestions)
    except Exception as error:  # noqa: BLE001
        outputs.warnings.append(f"AI redaction failed ({error}); fell back to lettered placeholders.")


def _generic_title(title: str) -> str:
    """A shareable title should not carry the product name from the detailed one."""
    return "Engineering contribution record"
