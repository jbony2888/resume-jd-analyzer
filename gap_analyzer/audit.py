"""Audit trail for model runs and API operations."""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent.parent / "logs"
AUDIT_FILE = AUDIT_DIR / "audit.log"
APP_LOG_FILE = AUDIT_DIR / "app.log"
MODEL_PERF_CSV = AUDIT_DIR / "model_performance.csv"

CSV_HEADERS = [
    "timestamp",
    "model",
    "use_mock",
    "match_score",
    "role_title",
    "candidate_name",
    "num_requirements",
    "num_matches",
    "num_missing",
    "num_gaps",
    "jd_char_count",
    "resume_char_count",
    "jd_hash",
    "resume_hash",
    "requirements_version",
    "requirements_source",
    "requirements_artifact_path",
    "requirements_hash",
    "prompt_version",
    "prompt_hash",
    "model_params",
    "normalized_requirement_count",
    "matched_count",
    "matched_count_raw",
    "matched_count_validated",
    "invalid_quote_count",
    "evidence_prompt_includes_description",
    "scoring_rationale",
    "criteria_used",
    "gap_details",
]


def _ensure_log_dir():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _iso_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def log_model_performance(
    *,
    model: str,
    use_mock: bool,
    match_score: int,
    role_title: str,
    candidate_name: str,
    criteria_used: list[dict],
    gap_report: list[dict],
    jd_char_count: int,
    resume_char_count: int,
    jd_hash: str | None = None,
    resume_hash: str | None = None,
    requirements_version: str | None = None,
    requirements_source: str | None = None,
    requirements_artifact_path: str | None = None,
    requirements_hash: str | None = None,
    prompt_version: str | None = None,
    prompt_hash: str | None = None,
    model_params: dict | None = None,
    normalized_requirement_count: int | None = None,
    matched_count: int | None = None,
    matched_count_raw: int | None = None,
    matched_count_validated: int | None = None,
    invalid_quote_count: int | None = None,
    evidence_prompt_includes_description: bool | None = None,
):
    """
    Log model performance for later review: time, criteria, why it scored that way.
    Writes to model_performance.json (append) and model_performance.csv.
    """
    _ensure_log_dir()
    ts = _iso_ts()

    num_reqs = len(criteria_used)
    num_matches = sum(1 for g in gap_report if g.get("status") == "MATCH")
    num_missing = sum(1 for g in gap_report if g.get("status") == "MISSING")
    num_gaps = sum(1 for g in gap_report if g.get("status") == "GAP")

    rationale_parts = [f"{num_matches} of {num_reqs} requirements matched ({match_score}%)."]
    if num_missing:
        missing_names = [g["name"] for g in gap_report if g.get("status") == "MISSING"]
        rationale_parts.append(f"Missing (must-have): {', '.join(missing_names)}.")
    if num_gaps:
        gap_names = [g["name"] for g in gap_report if g.get("status") == "GAP"]
        rationale_parts.append(f"Gaps (nice-to-have): {', '.join(gap_names)}.")
    scoring_rationale = " ".join(rationale_parts)

    entry = {
        "timestamp": ts,
        "model": model,
        "use_mock": use_mock,
        "match_score": match_score,
        "role_title": role_title,
        "candidate_name": candidate_name,
        "num_requirements": num_reqs,
        "num_matches": num_matches,
        "num_missing": num_missing,
        "num_gaps": num_gaps,
        "jd_char_count": jd_char_count,
        "resume_char_count": resume_char_count,
        "jd_hash": jd_hash,
        "resume_hash": resume_hash,
        "requirements_version": requirements_version,
        "requirements_source": requirements_source,
        "requirements_artifact_path": requirements_artifact_path,
        "requirements_hash": requirements_hash,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
        "model_params": model_params,
        "normalized_requirement_count": normalized_requirement_count or num_reqs,
        "matched_count": matched_count or num_matches,
        "matched_count_raw": matched_count_raw,
        "matched_count_validated": matched_count_validated,
        "invalid_quote_count": invalid_quote_count,
        "evidence_prompt_includes_description": evidence_prompt_includes_description,
        "scoring_rationale": scoring_rationale,
        "criteria_used": criteria_used,
        "gap_details": gap_report,
    }

    # Append to JSON (as JSONL for easy appending)
    jsonl_file = AUDIT_DIR / "model_performance.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    # Append to CSV
    csv_exists = MODEL_PERF_CSV.exists()
    with open(MODEL_PERF_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not csv_exists:
            writer.writeheader()
        row = {
            "timestamp": ts,
            "model": model,
            "use_mock": use_mock,
            "match_score": match_score,
            "role_title": role_title,
            "candidate_name": candidate_name,
            "num_requirements": num_reqs,
            "num_matches": num_matches,
            "num_missing": num_missing,
            "num_gaps": num_gaps,
            "jd_char_count": jd_char_count,
            "resume_char_count": resume_char_count,
            "jd_hash": jd_hash or "",
            "resume_hash": resume_hash or "",
            "requirements_version": requirements_version or "",
            "requirements_source": requirements_source or "",
            "requirements_artifact_path": requirements_artifact_path or "",
            "requirements_hash": requirements_hash or "",
            "prompt_version": prompt_version or "",
            "prompt_hash": prompt_hash or "",
            "model_params": json.dumps(model_params or {}),
            "normalized_requirement_count": normalized_requirement_count or num_reqs,
            "matched_count": matched_count or num_matches,
            "matched_count_raw": matched_count_raw if matched_count_raw is not None else "",
            "matched_count_validated": matched_count_validated if matched_count_validated is not None else "",
            "invalid_quote_count": invalid_quote_count if invalid_quote_count is not None else "",
            "evidence_prompt_includes_description": evidence_prompt_includes_description if evidence_prompt_includes_description is not None else "",
            "scoring_rationale": scoring_rationale,
            "criteria_used": json.dumps(criteria_used, default=str),
            "gap_details": json.dumps(gap_report, default=str),
        }
        writer.writerow(row)


def audit_log(
    action: str,
    status: str,
    *,
    use_mock: bool = False,
    model: str | None = None,
    jd_char_count: int | None = None,
    resume_char_count: int | None = None,
    match_score: int | None = None,
    filename: str | None = None,
    error: str | None = None,
    extra: dict | None = None,
):
    """Append a structured audit entry to the audit log (JSONL)."""
    _ensure_log_dir()
    entry = {
        "timestamp": _iso_ts(),
        "action": action,
        "status": status,
        "use_mock": use_mock,
    }
    if model:
        entry["model"] = model
    if jd_char_count is not None:
        entry["jd_char_count"] = jd_char_count
    if resume_char_count is not None:
        entry["resume_char_count"] = resume_char_count
    if match_score is not None:
        entry["match_score"] = match_score
    if filename:
        entry["filename"] = filename
    if error:
        entry["error"] = error
    if extra:
        entry.update(extra)

    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def setup_app_logging():
    """Configure application logging to console and file."""
    _ensure_log_dir()
    logger = logging.getLogger("gap_analyzer")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(ch)

    # File
    fh = logging.FileHandler(APP_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(fh)

    return logger
