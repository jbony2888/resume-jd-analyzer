"""Determinism test: same resume + same frozen requirements evaluated 10x → identical scores."""

import pytest

from src.scoring import compute_score


SAMPLE_REQUIREMENTS = {
    "role_id": "test_role",
    "jd_hash": "a" * 64,
    "requirements_version": "1.0.0",
    "created_at": "2025-01-01T00:00:00Z",
    "requirements": [
        {"id": "REQ-001", "category": "Technical", "name": "Python", "description": "Python experience", "must_have": True, "weight": 5},
        {"id": "REQ-002", "category": "Technical", "name": "SQL", "description": "SQL knowledge", "must_have": False, "weight": 3},
        {"id": "REQ-003", "category": "AI", "name": "LLMs", "description": "LLM experience", "must_have": True, "weight": 4},
    ],
}

SAMPLE_EVIDENCE_MAP = {
    "role_id": "test_role",
    "jd_hash": "a" * 64,
    "resume_hash": "b" * 64,
    "requirements_version": "1.0.0",
    "prompt_version": "1.0.0",
    "model_id": "test",
    "matches": [
        {"requirement_id": "REQ-001", "matched": True, "evidence": [{"quote": "Python developer", "resume_section": "Experience"}]},
        {"requirement_id": "REQ-002", "matched": True, "evidence": [{"quote": "SQL queries", "resume_section": "Skills"}]},
        {"requirement_id": "REQ-003", "matched": False, "evidence": []},
    ],
}


def test_compute_score_determinism():
    """Same inputs → identical scores across 10 runs."""
    results = []
    for _ in range(10):
        score = compute_score(SAMPLE_REQUIREMENTS, SAMPLE_EVIDENCE_MAP)
        results.append(score)

    first = results[0]
    for r in results[1:]:
        assert r == first
        assert r["overall_score"] == first["overall_score"]
        assert r["must_have_coverage"] == first["must_have_coverage"]
        assert r["nice_to_have_coverage"] == first["nice_to_have_coverage"]
        assert r["per_category_scores"] == first["per_category_scores"]
        assert r["total_matched"] == first["total_matched"]
        assert r["total_requirements"] == first["total_requirements"]
