from __future__ import annotations

import pytest

from app.analysis.models import Evidence, PRAnalysis, reject_unsupported_metrics
from app.github.models import PullRequest

from conftest import valid_analysis


def test_valid_llm_response_model_is_accepted():
    analysis = valid_analysis()
    assert analysis.career_evidence_score == 29


def test_invalid_json_or_schema_is_rejected():
    with pytest.raises(Exception):
        PRAnalysis.model_validate_json('{"pr_number": 12}')


def test_hallucinated_metric_is_rejected():
    analysis = valid_analysis()
    analysis.resume_bullets[0].bullet = "Reduced cache latency by 30%."
    with pytest.raises(ValueError, match="not supported"):
        reject_unsupported_metrics(analysis, ["Add cache configuration"])


def test_inference_cannot_claim_high_confidence():
    with pytest.raises(ValueError, match="cannot be high confidence"):
        Evidence(claim="Likely enables scale-out.", confidence="high", kind="reasonable_inference", supporting_facts=["Cache file changed"])


def test_score_total_is_validated():
    data = valid_analysis().model_dump()
    data["career_evidence_score"] = 100
    with pytest.raises(ValueError, match="must equal"):
        PRAnalysis.model_validate(data)
