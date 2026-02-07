"""Orchestrates the deterministic frozen-requirements pipeline for /api/analyze."""

import json

from src.utils import hash_text
from src.pipeline.artifacts import load_requirements_artifact_by_jd_hash, save_evidence_artifact
from src.pipeline.match import match_resume_to_requirements
from src.scoring import compute_score
from src.validation import validate_evidence_map as validate_evidence_map_schema


def _evidence_map_to_gap_report(requirements_doc: dict, evidence_map: dict) -> list[dict]:
    """Convert evidence map + requirements to UI gap_report format (status, evidence, etc)."""
    req_by_id = {r["id"]: r for r in requirements_doc.get("requirements", [])}
    match_by_id = {m["requirement_id"]: m for m in evidence_map.get("matches", [])}
    report = []
    for r in requirements_doc.get("requirements", []):
        m = match_by_id.get(r["id"], {})
        matched = m.get("matched", False)
        evidence_list = m.get("evidence") or []
        evidence_str = (
            evidence_list[0]["quote"] if evidence_list and evidence_list[0].get("quote") else "No evidence found."
        )
        if matched:
            status = "MATCH"
        elif r.get("must_have"):
            status = "MISSING"
        else:
            status = "GAP"
        report.append({
            "id": r["id"],
            "category": r.get("category", "Technical"),
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "importance": "Must-have" if r.get("must_have") else "Nice-to-have",
            "status": status,
            "evidence": evidence_str,
        })
    return report


def run_frozen_analysis(
    api_key: str,
    jd_text: str,
    resume_text: str,
) -> dict:
    """
    Run analysis using frozen requirements. NO fallback to extraction.
    Raises FileNotFoundError (409) if requirements artifact missing for this JD.
    Returns dict with jd_analysis, resume_analysis, gap_report, match_score, and audit fields.
    """
    jd_hash = hash_text(jd_text)
    resume_hash = hash_text(resume_text)

    requirements_doc, artifact_path = load_requirements_artifact_by_jd_hash(jd_hash)
    evidence_map = match_resume_to_requirements(api_key, resume_text, requirements_doc)
    validate_evidence_map_schema(evidence_map)
    # Save without _audit for clean artifact
    to_save = {k: v for k, v in evidence_map.items() if k not in ("_audit", "meta")}
    save_evidence_artifact(to_save)

    score_result = compute_score(requirements_doc, evidence_map, resume_text)
    gap_report = _evidence_map_to_gap_report(requirements_doc, evidence_map)

    requirements = requirements_doc.get("requirements", [])
    jd_analysis = {
        "role_title": requirements_doc.get("role_title", ""),
        "requirements": [
            {
                "category": r.get("category", "Technical"),
                "name": r.get("name", ""),
                "importance": "Must-have" if r.get("must_have") else "Nice-to-have",
                "description": r.get("description", ""),
            }
            for r in requirements
        ],
    }
    # Derive resume signals from matched requirements + evidence (for UI "EXTRACTED RESUME SIGNALS" panel)
    req_by_id = {r["id"]: r for r in requirements}
    signals = []
    for m in evidence_map.get("matches", []):
        if m.get("matched") and m.get("evidence"):
            ev = m["evidence"][0]
            req = req_by_id.get(m["requirement_id"], {})
            signals.append({
                "category": req.get("category", "Technical"),
                "name": req.get("name", ""),
                "evidence": ev.get("quote", ""),
                "years_experience": ev.get("years_experience"),  # may be absent
            })
    resume_analysis = {
        "candidate_name": evidence_map.get("candidate_name", ""),
        "signals": signals,
    }

    audit_info = evidence_map.get("_audit", {})
    meta = evidence_map.get("meta", {})
    requirements_hash = hash_text(json.dumps(requirements_doc, sort_keys=True))

    return {
        "model_id": evidence_map.get("model_id"),  # actual model used (match stage)
        "jd_analysis": jd_analysis,
        "resume_analysis": resume_analysis,
        "gap_report": gap_report,
        "match_score": int(round(score_result["overall_score"])),
        "jd_hash": jd_hash,
        "resume_hash": resume_hash,
        "requirements_version": requirements_doc.get("requirements_version", ""),
        "requirements_source": "artifact",
        "requirements_artifact_path": str(artifact_path),
        "num_requirements": len(requirements),
        "must_have_coverage": score_result.get("must_have_coverage"),
        "nice_to_have_coverage": score_result.get("nice_to_have_coverage"),
        "prompt_version": audit_info.get("prompt_version"),
        "prompt_hash": audit_info.get("prompt_hash"),
        "model_params": audit_info.get("model_params"),
        "matched_count": score_result.get("total_matched"),
        "matched_count_raw": meta.get("matched_count_raw"),
        "matched_count_validated": meta.get("matched_count_validated"),
        "invalid_quote_count": meta.get("invalid_quote_count"),
        "requirements_hash": requirements_hash,
        "evidence_prompt_includes_description": False,
    }
