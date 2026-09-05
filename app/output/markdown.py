"""Readable Markdown reports generated solely from validated structured output."""

from __future__ import annotations

from app.analysis.models import CareerHighlight, CareerProfile, PRAnalysis


def render_profile(profile: CareerProfile, analyses: list[PRAnalysis]) -> str:
    lines = ["# Engineering Career Profile", "", "## Executive Summary", "", profile.executive_summary, "", "## Core Strengths", ""]
    lines.extend(f"{index}. {strength}" for index, strength in enumerate(profile.core_strengths, 1))
    lines.extend(["", "## Strongest Career Evidence", ""])
    for index, highlight in enumerate(profile.strongest_career_evidence, 1):
        lines.extend(_highlight(index, highlight))
    lines.extend(["", "## Senior Engineer Signals", ""])
    lines.extend(_bullets(profile.senior_engineer_signals, "No senior-level conclusions were generated beyond the supplied evidence."))
    lines.extend(["", "## Technology Matrix", "", "| Technology | Evidence | Confidence |", "|---|---|---|"])
    lines.extend(f"| {item.technology} | {item.evidence} | {item.confidence} |" for item in profile.technology_matrix)
    lines.extend(["", "## Resume Bullets", ""])
    lines.extend(f"- {bullet.bullet}" for bullet in profile.resume_bullets)
    lines.extend(["", "## Interview Preparation", ""])
    for index, story in enumerate(profile.interview_stories, 1):
        lines.extend([f"### Story {index}: {story.title}", "", story.interview_story, ""])
    lines.extend(["## Evidence Gaps", ""])
    lines.extend(_bullets(profile.evidence_gaps, "No gaps identified."))
    lines.extend(["", "## Recommended Additional Evidence", ""])
    lines.extend(_bullets(profile.recommended_additional_evidence, "No additional evidence recommendations generated."))
    lines.extend(["", "## PR-Level Evidence", ""])
    for analysis in analyses:
        lines.extend(_pr_section(analysis))
    return "\n".join(lines).rstrip() + "\n"


def _highlight(index: int, highlight: CareerHighlight) -> list[str]:
    return [
        f"### {index}. {highlight.title}", "", f"**PRs:** {', '.join('#' + str(number) for number in highlight.pr_numbers)}", "",
        "**Evidence:**", *[f"- {item}" for item in highlight.evidence], "", f"**Why it matters:** {highlight.why_it_matters}", "",
        f"**Confidence:** {highlight.confidence}", "", f"**Resume bullet:** {highlight.resume_bullet}", "",
        f"**Interview story:** {highlight.interview_story}", "",
    ]


def _pr_section(analysis: PRAnalysis) -> list[str]:
    lines = [f"### PR #{analysis.pr_number}: {analysis.title}", "", analysis.summary, "", f"**Career evidence score:** {analysis.career_evidence_score}/100 (heuristic, not code quality)", ""]
    lines.append("**Score rationale:**")
    lines.extend(f"- {item.dimension.replace('_', ' ')}: {item.explanation}" for item in analysis.score_explanations)
    lines.extend(["", "**Evidence:**"])
    for evidence in analysis.evidence:
        lines.append(f"- [{evidence.kind}; {evidence.confidence} confidence] {evidence.claim}")
        lines.extend(f"  - {fact}" for fact in evidence.supporting_facts)
    lines.extend(["", "**Defensible resume options:**"])
    lines.extend(f"- {bullet.bullet}" for bullet in analysis.resume_bullets)
    lines.extend(["", "**Interview story:**"])
    story = analysis.interview_story
    for label, value in (("Problem", story.problem), ("Context", story.context), ("Constraints", story.constraints), ("Options considered", story.options_considered), ("Decision", story.decision), ("Implementation", story.implementation), ("Trade-offs", story.trade_offs), ("Result", story.result), ("What I would improve", story.what_i_would_improve)):
        lines.append(f"- **{label}:** {value}")
    lines.extend(["", "**PR-specific interview questions:**"])
    lines.extend(f"- {question}" for question in analysis.interview_questions)
    if analysis.risks_or_uncertainties:
        lines.extend(["", "**Risks or uncertainties:**"])
        lines.extend(f"- {risk}" for risk in analysis.risks_or_uncertainties)
    lines.append("")
    return lines


def _bullets(items: list[str], fallback: str) -> list[str]:
    return [*(f"- {item}" for item in items)] if items else [f"- {fallback}"]

