"""
Idempotency test: run same (resume, JD) N times; assert identical outputs.
Requires GROQ_API_KEY for full E2E. Skips if not set.
"""

import os
import pytest

from src.utils import hash_text
from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.normalize import normalize_requirements
from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact_by_jd_hash
from src.pipeline.match import match_resume_to_requirements
from src.scoring import compute_score

N_RUNS = 10

# Fixture paths relative to project root
FIXTURE_JD_PATH = "sample_jd.txt"
FIXTURE_RESUME_PATH = "resumes/master/Master-Copy-Resume.pdf"


def _read_fixture_jd():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / FIXTURE_JD_PATH
    if not p.exists():
        pytest.skip(f"Fixture JD not found: {p}")
    return p.read_text(encoding="utf-8")


def _read_fixture_resume():
    from pathlib import Path
    from gap_analyzer import extract_text_from_pdf
    p = Path(__file__).resolve().parent.parent / FIXTURE_RESUME_PATH
    if not p.exists():
        pytest.skip(f"Fixture resume not found: {p}")
    return extract_text_from_pdf(p)


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_extract_normalize_idempotency():
    """Run extract + normalize 10x; assert normalized requirement ids and keys identical."""
    api_key = os.environ["GROQ_API_KEY"]
    jd_text = _read_fixture_jd()

    results = []
    for _ in range(N_RUNS):
        doc = extract_requirements_from_jd(api_key, jd_text)
        reqs = doc["requirements"]
        results.append({
            "ids": [r["id"] for r in reqs],
            "keys": [r.get("requirement_key", "") for r in reqs],
            "names": [r["name"] for r in reqs],
        })

    first = results[0]
    for i, r in enumerate(results[1:], start=1):
        if r["ids"] != first["ids"]:
            diff = set(r["ids"]) ^ set(first["ids"])
            pytest.fail(f"Run {i+1}: requirement ids differ. Diff: {diff}")
        if r["keys"] != first["keys"]:
            diff = [(a, b) for a, b in zip(r["keys"], first["keys"]) if a != b]
            pytest.fail(f"Run {i+1}: requirement_keys differ. Diff: {diff}")
        if r["names"] != first["names"]:
            pytest.fail(f"Run {i+1}: requirement names differ")


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_match_score_idempotency():
    """With frozen requirements, run match+score 10x; assert identical matches and score."""
    api_key = os.environ["GROQ_API_KEY"]
    jd_text = _read_fixture_jd()
    resume_text = _read_fixture_resume()
    jd_hash = hash_text(jd_text)

    # Ensure artifact exists
    try:
        requirements_doc, _ = load_requirements_artifact_by_jd_hash(jd_hash)
    except FileNotFoundError:
        doc = extract_requirements_from_jd(api_key, jd_text)
        save_requirements_artifact(
            doc["role_id"],
            doc["jd_hash"],
            doc,
        )
        requirements_doc = load_requirements_artifact_by_jd_hash(jd_hash)[0]

    results = []
    for _ in range(N_RUNS):
        evidence_map = match_resume_to_requirements(api_key, resume_text, requirements_doc)
        score = compute_score(requirements_doc, evidence_map)
        match_by_id = {m["requirement_id"]: m["matched"] for m in evidence_map["matches"]}
        results.append({
            "matched": match_by_id,
            "score": score["overall_score"],
            "total_matched": score["total_matched"],
        })

    first = results[0]
    for i, r in enumerate(results[1:], start=1):
        if r["matched"] != first["matched"]:
            diff = {
                k: (r["matched"].get(k), first["matched"].get(k))
                for k in set(r["matched"]) | set(first["matched"])
                if r["matched"].get(k) != first["matched"].get(k)
            }
            pytest.fail(f"Run {i+1}: matched booleans differ. Diff: {diff}")
        if r["score"] != first["score"]:
            pytest.fail(f"Run {i+1}: score {r['score']} != {first['score']}")
        if r["total_matched"] != first["total_matched"]:
            pytest.fail(f"Run {i+1}: total_matched {r['total_matched']} != {first['total_matched']}")


def test_normalize_deterministic():
    """Unit test: same raw input -> same normalized output (no LLM)."""
    raw = [
        {"name": "Python 3", "category": "Technical", "must_have": True, "description": "Python experience"},
        {"name": "python3", "category": "Technical", "must_have": False, "description": "Python 3"},
    ]
    r1 = normalize_requirements(raw)
    r2 = normalize_requirements(raw)
    assert [x["id"] for x in r1] == [x["id"] for x in r2]
    assert [x["requirement_key"] for x in r1] == [x["requirement_key"] for x in r2]
    assert len(r1) == len(r2)
    # Should merge near-duplicates
    assert len(r1) <= 2
