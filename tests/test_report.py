"""Tests for redaction and the two-version build.

The leak test is the important one here: a bug in redaction publishes an
employer's internal names, so it is checked against the rendered bytes rather
than against the model that produced them.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.analysis import portfolio as portfolio_module
from app.gitlog.models import BACKEND, FRONTEND, BranchStat, Commit, RepoReport
from app.report import build as report_build
from app.report import guide as guide_module
from app.report.html import DETAILED, SHAREABLE
from app.report.redact import Redactor, apply_llm_terms

SECRETS = ["Northwind", "Lakeside", "AcmePort", "ACME-", "order-management", "backendRepo"]


def _commit(sha: str, repo: str, subject: str, path: str, when=date(2026, 1, 2)) -> Commit:
    return Commit(
        sha=sha, date=when, author_name="Dana Reed", author_email="a@b.com",
        subject=subject, repo=repo, insertions=10, deletions=2, files=1, paths=(path,),
    )


@pytest.fixture
def sample_portfolio():
    backend = RepoReport(
        label="backendRepo", path=Path("."), kind=BACKEND, trunk="origin/main",
        commits=[
            _commit("1", "backendRepo", "[ACME-101] reconciliation fix (#11)", "src/order-management/calc.cs"),
            _commit("2", "backendRepo", "version 9.8.17", "src/order-management/ver.cs"),
        ],
        branches=[
            BranchStat(repo="backendRepo", name="origin/Client/Northwind", mine=40, total=100,
                       first=date(2025, 1, 1), last=date(2026, 1, 1), kind="client"),
            BranchStat(repo="backendRepo", name="origin/RELEASE-Lakeside", mine=20, total=22,
                       first=date(2026, 7, 1), last=date(2026, 8, 1), kind="release"),
        ],
        test_touches=1, total_touches=20, team_test_touches=3, team_total_touches=60,
        offtrunk_commits=60,
    )
    frontend = RepoReport(
        label="frontendRepo", path=Path("."), kind=FRONTEND, trunk="origin/main",
        commits=[_commit("3", "frontendRepo", "[ACME-102] planner ui (#12)", "src/order-management/ui.ts")],
    )
    return portfolio_module.build([backend, frontend], ["a@b.com"])


# ----- redactor -----------------------------------------------------


def test_placeholders_are_stable_and_grouped_by_type(sample_portfolio):
    redactor = Redactor(sample_portfolio)
    names = set(redactor.branches.values())
    assert "Release line A" in names
    assert "Client deployment A" in names
    assert Redactor(sample_portfolio).branches == redactor.branches, "mapping must be deterministic"


def test_apply_replaces_names_but_never_numbers(sample_portfolio):
    redacted = Redactor(sample_portfolio).apply(sample_portfolio)

    assert redacted.commits == sample_portfolio.commits
    assert redacted.insertions == sample_portfolio.insertions
    assert redacted.release_cuts == sample_portfolio.release_cuts
    assert [b.mine for b in redacted.branches] == [b.mine for b in sample_portfolio.branches]
    assert [b.share for b in redacted.branches] == [b.share for b in sample_portfolio.branches]

    for branch in redacted.branches:
        assert "Northwind" not in branch.name
        assert "Lakeside" not in branch.name


def test_branch_type_survives_redaction(sample_portfolio):
    redacted = Redactor(sample_portfolio).apply(sample_portfolio)
    kinds = {b.kind for b in redacted.branches}
    assert kinds == {"client", "release"}, "kind must not be re-derived from the placeholder name"


def test_scrub_replaces_identifiers_in_free_text(sample_portfolio):
    redactor = Redactor(sample_portfolio)
    text = "Led the Client/Northwind rollout and the ACME-101 migration."
    scrubbed = redactor.scrub(text)
    assert "Northwind" not in scrubbed
    assert "ACME" not in scrubbed


def test_legend_maps_back_and_is_marked_local(sample_portfolio):
    redactor = Redactor(sample_portfolio)
    text = redactor.legend_text()
    assert "KEEP THIS FILE LOCAL" in text
    assert "origin/Client/Northwind" in text, "the key is the one file that holds the real names"


def test_llm_terms_override_lettered_placeholders(sample_portfolio):
    redactor = Redactor(sample_portfolio)
    apply_llm_terms(redactor, {"origin/Client/Northwind": "a national logistics operator"})
    assert redactor.branches["origin/Client/Northwind"] == "a national logistics operator"


def test_llm_terms_ignore_unknown_and_blank_values(sample_portfolio):
    redactor = Redactor(sample_portfolio)
    before = dict(redactor.branches)
    apply_llm_terms(redactor, {"origin/Client/Northwind": "   ", "not-a-real-branch": "x"})
    assert redactor.branches == before


# ----- guide --------------------------------------------------------


def test_guide_prompts_are_anchored_to_measured_evidence(sample_portfolio):
    redacted = Redactor(sample_portfolio).apply(sample_portfolio)
    drafting = guide_module.build(redacted, ["Client deployment A"])
    assert drafting.prompts
    assert any(prompt.evidence for prompt in drafting.prompts)
    assert any("missing entirely" in prompt.heading.lower() for prompt in drafting.prompts)


def test_guide_bullets_carry_real_numbers_and_blank_slots(sample_portfolio):
    redacted = Redactor(sample_portfolio).apply(sample_portfolio)
    drafting = guide_module.build(redacted, [])
    joined = " ".join(drafting.bullets)
    assert f"{sample_portfolio.commits:,}" in joined
    assert "[" in joined and "]" in joined, "bullets must show what the author still has to supply"


# ----- build --------------------------------------------------------


def test_both_versions_are_written(sample_portfolio, tmp_path: Path):
    result = report_build.generate(sample_portfolio, tmp_path, report_build.Options(title="Acme record"))
    written = {p.name for p in result.files}
    assert written == {"report.html", "report.md", "report.json", "redaction-key.txt"}
    assert (tmp_path / "detailed" / "report.html").exists()
    assert (tmp_path / "shareable" / "report.html").exists()
    assert not result.warnings


def test_only_the_requested_version_is_written(sample_portfolio, tmp_path: Path):
    report_build.generate(sample_portfolio, tmp_path, report_build.Options(versions=(SHAREABLE,)))
    assert not (tmp_path / "detailed").exists()
    assert (tmp_path / "shareable" / "report.html").exists()


def test_shareable_output_contains_no_internal_names(sample_portfolio, tmp_path: Path):
    """The one that matters. Checked against rendered bytes, in every format."""
    report_build.generate(
        sample_portfolio, tmp_path,
        report_build.Options(
            title="AcmePort contribution record",
            subtitle="Six years on AcmePort in Lakeside.",
            author_name="Dana Reed",
        ),
    )
    for name in ("report.html", "report.md", "report.json"):
        text = (tmp_path / "shareable" / name).read_text(encoding="utf-8")
        for secret in SECRETS:
            assert secret.lower() not in text.lower(), f"{secret} leaked into shareable/{name}"


def test_detailed_output_keeps_internal_names(sample_portfolio, tmp_path: Path):
    report_build.generate(sample_portfolio, tmp_path, report_build.Options(title="AcmePort record"))
    text = (tmp_path / "detailed" / "report.html").read_text(encoding="utf-8")
    assert "Northwind" in text and "AcmePort" in text


def test_author_name_appears_in_both_versions(sample_portfolio, tmp_path: Path):
    report_build.generate(sample_portfolio, tmp_path, report_build.Options(author_name="Dana Reed"))
    for version in ("detailed", "shareable"):
        assert "Dana Reed" in (tmp_path / version / "report.html").read_text(encoding="utf-8")


def test_shareable_json_keeps_the_figures(sample_portfolio, tmp_path: Path):
    report_build.generate(sample_portfolio, tmp_path, report_build.Options(versions=(SHAREABLE,)))
    data = json.loads((tmp_path / "shareable" / "report.json").read_text(encoding="utf-8"))
    assert data["totals"]["commits"] == sample_portfolio.commits
    assert data["totals"]["insertions"] == sample_portfolio.insertions


def test_ai_requested_without_a_key_falls_back_and_warns(sample_portfolio, tmp_path: Path):
    result = report_build.generate(
        sample_portfolio, tmp_path, report_build.Options(use_ai=True, api_key="   ")
    )
    assert result.ai_used is False
    assert any("no API key" in w for w in result.warnings)
    assert (tmp_path / "detailed" / "report.html").exists(), "a missing key must not lose the report"


def test_ai_failure_degrades_to_the_offline_report(sample_portfolio, tmp_path: Path, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(report_build.narrative, "draft_work_streams", explode)
    result = report_build.generate(
        sample_portfolio, tmp_path,
        report_build.Options(use_ai=True, api_key="sk-test", versions=(DETAILED,)),
    )
    assert result.ai_used is False
    assert any("provider unavailable" in w for w in result.warnings)
    assert (tmp_path / "detailed" / "report.html").exists()


def test_offline_report_states_nothing_was_uploaded(sample_portfolio, tmp_path: Path):
    report_build.generate(sample_portfolio, tmp_path, report_build.Options(versions=(DETAILED,)))
    text = (tmp_path / "detailed" / "report.html").read_text(encoding="utf-8")
    assert "no language model saw any code" in text
