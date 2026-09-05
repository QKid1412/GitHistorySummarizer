"""Pydantic models for validated LLM output and final career synthesis."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Confidence = Literal["high", "medium", "low"]

ENGINEERING_CATEGORIES = [
    "Backend Engineering", "Frontend Engineering", "Distributed Systems", "System Design", "Cloud / Azure",
    "Database / SQL", "Performance Optimization", "Security", "Authentication / Authorization", "Caching",
    "Messaging", "Kafka / Event-driven Architecture", "API Design", "Microservices", "Reliability",
    "Observability", "Testing", "DevOps / CI/CD", "Infrastructure", "Architecture", "Refactoring",
    "Code Quality", "Technical Leadership", "Cross-team Collaboration", "Product / Business Impact",
]


class Evidence(BaseModel):
    claim: str = Field(min_length=1)
    confidence: Confidence
    supporting_facts: list[str] = Field(min_length=1)
    kind: Literal["fact", "reasonable_inference"] = "fact"

    @model_validator(mode="after")
    def confidence_matches_kind(self) -> "Evidence":
        if self.kind == "reasonable_inference" and self.confidence == "high":
            raise ValueError("Reasonable inferences cannot be high confidence.")
        return self


class ResumeBullet(BaseModel):
    bullet: str = Field(min_length=10, max_length=350)
    evidence: list[str] = Field(min_length=1)

    @field_validator("bullet")
    @classmethod
    def avoid_empty_buzzwords(cls, value: str) -> str:
        forbidden = ("leveraged", "synergized", "spearheaded", "revolutionized", "cutting-edge")
        if any(word in value.lower() for word in forbidden):
            raise ValueError("Resume bullet contains prohibited buzzword language.")
        return value


class ScoreExplanation(BaseModel):
    dimension: Literal["technical_complexity", "ownership", "architecture", "impact", "senior_signal"]
    explanation: str = Field(min_length=5)


class InterviewStory(BaseModel):
    problem: str
    context: str
    constraints: str
    options_considered: str
    decision: str
    implementation: str
    trade_offs: str
    result: str
    what_i_would_improve: str


class PRAnalysis(BaseModel):
    pr_number: int
    title: str
    summary: str
    engineering_categories: list[str] = Field(default_factory=list)
    technical_complexity: int = Field(ge=0, le=20)
    ownership: int = Field(ge=0, le=20)
    architecture_score: int = Field(ge=0, le=20)
    impact_score: int = Field(ge=0, le=20)
    senior_signal_score: int = Field(ge=0, le=20)
    career_evidence_score: int = Field(ge=0, le=100)
    score_explanations: list[ScoreExplanation] = Field(min_length=5, max_length=5)
    key_contributions: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    resume_bullets: list[ResumeBullet] = Field(default_factory=list, max_length=3)
    interview_story: InterviewStory
    interview_questions: list[str] = Field(min_length=5, max_length=10)
    risks_or_uncertainties: list[str] = Field(default_factory=list)

    @field_validator("engineering_categories")
    @classmethod
    def known_categories(cls, categories: list[str]) -> list[str]:
        invalid = set(categories) - set(ENGINEERING_CATEGORIES)
        if invalid:
            raise ValueError(f"Unknown engineering categories: {', '.join(sorted(invalid))}")
        return categories

    @model_validator(mode="after")
    def total_is_consistent(self) -> "PRAnalysis":
        total = self.technical_complexity + self.ownership + self.architecture_score + self.impact_score + self.senior_signal_score
        if self.career_evidence_score != total:
            raise ValueError("career_evidence_score must equal the five component scores.")
        dimensions = {item.dimension for item in self.score_explanations}
        if len(dimensions) != 5:
            raise ValueError("Each score dimension must have one explanation.")
        return self


class CareerHighlight(BaseModel):
    title: str
    pr_numbers: list[int] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    why_it_matters: str
    confidence: Confidence
    resume_bullet: str
    interview_story: str


class TechnologyEvidence(BaseModel):
    technology: str
    evidence: str
    confidence: Confidence


class CareerProfile(BaseModel):
    executive_summary: str
    core_strengths: list[str] = Field(min_length=1, max_length=10)
    strongest_career_evidence: list[CareerHighlight] = Field(min_length=1, max_length=10)
    senior_engineer_signals: list[str] = Field(default_factory=list)
    technology_matrix: list[TechnologyEvidence] = Field(default_factory=list)
    resume_bullets: list[ResumeBullet] = Field(min_length=5, max_length=10)
    interview_stories: list[CareerHighlight] = Field(min_length=3, max_length=5)
    evidence_gaps: list[str] = Field(default_factory=list)
    recommended_additional_evidence: list[str] = Field(default_factory=list)


METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|x\b|ms\b|seconds?\b|minutes?\b|hours?\b|customers?\b|users?\b)", re.I)


def reject_unsupported_metrics(analysis: PRAnalysis, source_facts: list[str]) -> None:
    """Reject generated outcome metrics unless their exact numerical evidence was supplied."""
    source_numbers = set(METRIC_PATTERN.findall(" ".join(source_facts)))
    generated = [analysis.summary, *analysis.key_contributions, *(bullet.bullet for bullet in analysis.resume_bullets)]
    for text in generated:
        for metric in METRIC_PATTERN.findall(text):
            if metric not in source_numbers:
                raise ValueError(f"Generated metric '{metric}' is not supported by supplied GitHub evidence.")

