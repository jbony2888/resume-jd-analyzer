"""Generate run_report.json for auditability."""

import json
from pathlib import Path

from src.utils import iso_now


def write_run_report(
    output_path: Path,
    role_id: str,
    jd_hash: str,
    resume_hash: str,
    requirements_version: str,
    prompt_version: str,
    model_id: str,
    run_id: str,
    score_result: dict,
    total_requirements: int,
    total_matched: int,
) -> None:
    """
    Write run_report.json with hashes, versions, counts, category scores.
    No PHI/PII beyond metadata hashes.
    """
    report = {
        "run_id": run_id,
        "timestamp": iso_now(),
        "role_id": role_id,
        "jd_hash": jd_hash,
        "resume_hash": resume_hash,
        "requirements_version": requirements_version,
        "prompt_version": prompt_version,
        "model_id": model_id,
        "total_requirements": total_requirements,
        "total_matched": total_matched,
        "must_have_coverage": score_result.get("must_have_coverage"),
        "nice_to_have_coverage": score_result.get("nice_to_have_coverage"),
        "overall_score": score_result.get("overall_score"),
        "per_category_scores": score_result.get("per_category_scores", {}),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
