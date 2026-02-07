"""Evidence validity test: matched=true without evidence quote is rejected."""

import pytest

from src.scoring import compute_score
from src.scoring.engine import EvidenceRequiredError


SAMPLE_REQUIREMENTS = {
    "role_id": "test",
    "jd_hash": "a" * 64,
    "requirements_version": "1.0.0",
    "created_at": "2025-01-01T00:00:00Z",
    "requirements": [
        {"id": "REQ-001", "category": "Technical", "name": "Python", "description": "", "must_have": True, "weight": 5},
    ],
}


def test_matched_true_without_evidence_raises():
    """matched=true with empty evidence array raises EvidenceRequiredError."""
    evidence_map = {
        "role_id": "test",
        "jd_hash": "a" * 64,
        "resume_hash": "b" * 64,
        "requirements_version": "1.0.0",
        "prompt_version": "1.0.0",
        "model_id": "test",
        "matches": [
            {"requirement_id": "REQ-001", "matched": True, "evidence": []},
        ],
    }
    with pytest.raises(EvidenceRequiredError) as exc_info:
        compute_score(SAMPLE_REQUIREMENTS, evidence_map)
    assert "REQ-001" in str(exc_info.value)
    assert "no evidence" in str(exc_info.value).lower()


def test_matched_true_with_evidence_none_raises():
    """matched=true with evidence=[{...}] but no quote raises EvidenceRequiredError."""
    evidence_map = {
        "role_id": "test",
        "jd_hash": "a" * 64,
        "resume_hash": "b" * 64,
        "requirements_version": "1.0.0",
        "prompt_version": "1.0.0",
        "model_id": "test",
        "matches": [
            {"requirement_id": "REQ-001", "matched": True, "evidence": [{"resume_section": "Skills"}]},
        ],
    }
    with pytest.raises(EvidenceRequiredError):
        compute_score(SAMPLE_REQUIREMENTS, evidence_map)


def test_matched_true_with_valid_evidence_succeeds():
    """matched=true with at least one evidence item containing quote succeeds."""
    evidence_map = {
        "role_id": "test",
        "jd_hash": "a" * 64,
        "resume_hash": "b" * 64,
        "requirements_version": "1.0.0",
        "prompt_version": "1.0.0",
        "model_id": "test",
        "matches": [
            {"requirement_id": "REQ-001", "matched": True, "evidence": [{"quote": "Python developer", "resume_section": "Experience"}]},
        ],
    }
    score = compute_score(SAMPLE_REQUIREMENTS, evidence_map)
    assert score["overall_score"] == 100
    assert score["total_matched"] == 1


def test_matched_false_with_empty_evidence_succeeds():
    """matched=false with empty evidence is valid."""
    evidence_map = {
        "role_id": "test",
        "jd_hash": "a" * 64,
        "resume_hash": "b" * 64,
        "requirements_version": "1.0.0",
        "prompt_version": "1.0.0",
        "model_id": "test",
        "matches": [
            {"requirement_id": "REQ-001", "matched": False, "evidence": []},
        ],
    }
    score = compute_score(SAMPLE_REQUIREMENTS, evidence_map)
    assert score["overall_score"] == 0
    assert score["total_matched"] == 0
