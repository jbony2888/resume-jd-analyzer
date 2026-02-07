"""Quote validation: invalid quotes (not in resume) are rejected; matched flipped to false."""

import pytest

from src.scoring.quote_validation import normalize_text, validate_evidence_quotes


def test_normalize_text():
    assert normalize_text("  hello   world  ") == "hello world"
    assert normalize_text("a\nb\tc") == "a b c"
    assert normalize_text("") == ""


def test_invalid_quote_flips_matched_to_false():
    """Quote not in resume -> matched=false, evidence cleared, invalid_quote=True."""
    resume_text = "Hello world"
    evidence_map = {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "matched": True,
                "evidence": [{"quote": "Not in resume"}],
            },
        ],
    }
    result = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    m = result["matches"][0]
    assert m["matched"] is False
    assert m["evidence"] == []
    assert m["invalid_quote"] is True
    assert result["meta"]["invalid_quote_count"] == 1
    assert result["meta"]["matched_count_raw"] == 1
    assert result["meta"]["matched_count_validated"] == 0


def test_valid_quote_passes():
    """Quote is exact substring -> matched stays True."""
    resume_text = "Built Python microservices with FastAPI"
    evidence_map = {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "matched": True,
                "evidence": [{"quote": "Python microservices with FastAPI"}],
            },
        ],
    }
    result = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    m = result["matches"][0]
    assert m["matched"] is True
    assert len(m["evidence"]) == 1
    assert m["invalid_quote"] is False
    assert result["meta"]["invalid_quote_count"] == 0
    assert result["meta"]["matched_count_validated"] == 1


def test_quote_too_short_rejected():
    """Quote below min_len -> invalid."""
    resume_text = "Python"
    evidence_map = {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "matched": True,
                "evidence": [{"quote": "Python"}],
            },
        ],
    }
    result = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    m = result["matches"][0]
    assert m["matched"] is False
    assert m["evidence"] == []
    assert m["invalid_quote"] is True


def test_whitespace_normalization():
    """Normalized quote matches resume despite different whitespace (extra spaces)."""
    resume_text = "Built  Python   microservices"
    evidence_map = {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "matched": True,
                "evidence": [{"quote": "Built Python microservices"}],
            },
        ],
    }
    result = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    m = result["matches"][0]
    assert m["matched"] is True
    assert m["invalid_quote"] is False


def test_whitespace_normalization_newlines_and_multiple_spaces():
    """
    Quote with newlines/multiple spaces; resume has same text with different whitespace.
    Validator should pass - prevents false invalidations due to PDF/formatting artifacts.
    """
    # Resume: newlines and tabs (e.g. from PDF extraction)
    resume_text = "Led cross-functional teams\n\nand delivered  Python  APIs"
    # Quote: model returns with different whitespace
    evidence_map = {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "matched": True,
                "evidence": [{"quote": "Led cross-functional teams and delivered Python APIs"}],
            },
        ],
    }
    result = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    m = result["matches"][0]
    assert m["matched"] is True
    assert m["invalid_quote"] is False
    assert result["meta"]["invalid_quote_count"] == 0


def test_e2e_negative_control_jd_echo_invalidated():
    """
    End-to-end negative control: JD text as evidence quote gets invalidated, score decreases.
    Simulates model echoing JD; guardrails must catch it.
    """
    import copy

    from src.scoring.quote_validation import validate_evidence_quotes
    from src.scoring.engine import compute_score

    resume_text = "I built Python APIs with FastAPI"
    jd_echo_quote = "Infrastructure: AWS (Fargate, ECS, S3, and more)"  # JD text, NOT in resume

    requirements_doc = {
        "requirements": [
            {"id": "REQ-001", "name": "Python", "must_have": True},
            {"id": "REQ-002", "name": "AWS", "must_have": True},
        ],
    }

    evidence_map_raw = {
        "matches": [
            {"requirement_id": "REQ-001", "matched": True, "evidence": [{"quote": "Python APIs with FastAPI"}]},
            {"requirement_id": "REQ-002", "matched": True, "evidence": [{"quote": jd_echo_quote}]},
        ],
    }

    # Without validation: both matched -> 100%
    em_unvalidated = copy.deepcopy(evidence_map_raw)
    score_unvalidated = compute_score(requirements_doc, em_unvalidated, resume_text=None)
    assert score_unvalidated["overall_score"] == 100
    assert score_unvalidated["total_matched"] == 2

    # With validation: JD echo invalidated -> 50%
    validate_evidence_quotes(resume_text, evidence_map_raw, min_len=12)
    score_validated = compute_score(requirements_doc, evidence_map_raw, resume_text)
    assert score_validated["overall_score"] == 50
    assert score_validated["total_matched"] == 1
    assert evidence_map_raw["meta"]["invalid_quote_count"] == 1
    assert evidence_map_raw["matches"][1]["matched"] is False
    assert evidence_map_raw["matches"][1]["evidence"] == []
