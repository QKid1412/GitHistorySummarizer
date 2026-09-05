from __future__ import annotations

from app.analysis.models import InterviewStory, PRAnalysis, ResumeBullet, ScoreExplanation


def valid_analysis(pr_number: int = 12, title: str = "Add cache configuration") -> PRAnalysis:
    return PRAnalysis(
        pr_number=pr_number,
        title=title,
        summary="Adds a cache configuration path and tests it.",
        engineering_categories=["Caching", "Testing"],
        technical_complexity=8,
        ownership=6,
        architecture_score=6,
        impact_score=4,
        senior_signal_score=5,
        career_evidence_score=29,
        score_explanations=[
            ScoreExplanation(dimension="technical_complexity", explanation="Changes configuration and cache behavior."),
            ScoreExplanation(dimension="ownership", explanation="The PR contains an end-to-end implementation."),
            ScoreExplanation(dimension="architecture", explanation="Cache integration is visible but limited in scope."),
            ScoreExplanation(dimension="impact", explanation="No measured production outcome is supplied."),
            ScoreExplanation(dimension="senior_signal", explanation="Tests and explicit trade-offs provide modest signal."),
        ],
        key_contributions=["Added a cache configuration path."],
        evidence=[{"claim": "The PR adds cache configuration.", "confidence": "high", "kind": "fact", "supporting_facts": ["Title: Add cache configuration"]}],
        resume_bullets=[ResumeBullet(bullet="Implemented cache configuration with accompanying tests.", evidence=["Changed cache configuration files and tests."])],
        interview_story=InterviewStory(problem="Cache behavior needed configuration.", context="A repository PR.", constraints="No production metrics are supplied.", options_considered="Only the implemented option is visible.", decision="Add configuration.", implementation="Updated cache-related files and tests.", trade_offs="Runtime behavior is not demonstrated in the PR.", result="The repository contains the configuration change.", what_i_would_improve="Validate behavior with production telemetry."),
        interview_questions=["Why was cache configuration needed?", "How would you validate cache availability?", "What invalidation strategy is required?", "What alternatives did you consider?", "How would this behave at higher load?"],
        risks_or_uncertainties=["No production outcome is visible."],
    )
