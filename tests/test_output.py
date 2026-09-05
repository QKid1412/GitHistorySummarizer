from __future__ import annotations

from datetime import datetime

from app.analysis.models import CareerHighlight, CareerProfile, ResumeBullet, TechnologyEvidence
from app.output.json_output import create_run_directory, write_json
from app.output.markdown import render_profile

from conftest import valid_analysis


def profile() -> CareerProfile:
    highlight = CareerHighlight(title="Cache configuration", pr_numbers=[12], evidence=["PR #12 changes cache configuration."], why_it_matters="Shows configuration and testing work.", confidence="high", resume_bullet="Implemented cache configuration with tests.", interview_story="Discuss cache configuration choices.")
    bullet = ResumeBullet(bullet="Implemented cache configuration with accompanying tests.", evidence=["PR #12"])
    return CareerProfile(executive_summary="Evidence is limited to one mocked PR.", core_strengths=["Caching"], strongest_career_evidence=[highlight], senior_engineer_signals=["Tests are visible."], technology_matrix=[TechnologyEvidence(technology="Cache", evidence="PR #12", confidence="high")], resume_bullets=[bullet, bullet, bullet, bullet, bullet], interview_stories=[highlight, highlight, highlight], evidence_gaps=["No production metrics."], recommended_additional_evidence=["Add incident or benchmark evidence."])


def test_markdown_generation_contains_required_sections():
    content = render_profile(profile(), [valid_analysis()])
    assert "# Engineering Career Profile" in content
    assert "## Resume Bullets" in content
    assert "[fact; high confidence]" in content


def test_json_serialization_handles_pydantic_lists(tmp_path):
    destination = tmp_path / "analysis.json"
    write_json(destination, [valid_analysis()])
    assert '"pr_number": 12' in destination.read_text(encoding="utf-8")


def test_timestamped_output_directory_never_overwrites(tmp_path):
    now = datetime(2026, 8, 25, 21, 0, 0)
    first = create_run_directory(tmp_path, now)
    second = create_run_directory(tmp_path, now)
    assert first.name == "2026-08-25_210000"
    assert second.name == "2026-08-25_210000_01"
