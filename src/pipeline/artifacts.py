"""Artifact storage: requirements and evidence maps."""

import json
from pathlib import Path

from src.validation import validate_requirements

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"


def _ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


def save_requirements_artifact(role_id: str, jd_hash: str, requirements_doc: dict) -> Path:
    """Save frozen requirements. Filename: job_requirements.<role_id>.<jd_hash>.v1.json"""
    validate_requirements(requirements_doc)
    _ensure_artifacts_dir()
    safe_role = "".join(c if c.isalnum() or c in "-_" else "_" for c in role_id)
    filename = f"job_requirements.{safe_role}.{jd_hash}.v1.json"
    path = ARTIFACTS_DIR / filename
    path.write_text(json.dumps(requirements_doc, indent=2), encoding="utf-8")
    return path


def load_requirements_artifact(role_id: str, jd_hash: str) -> dict:
    """
    Load frozen requirements. FAILS (raises) if artifact missing.
    No silent regeneration.
    """
    safe_role = "".join(c if c.isalnum() or c in "-_" else "_" for c in role_id)
    filename = f"job_requirements.{safe_role}.{jd_hash}.v1.json"
    path = ARTIFACTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Requirements artifact not found: {path}. "
            "Run Stage A (extract + save) first. No automatic regeneration."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_requirements_artifact_by_jd_hash(jd_hash: str) -> tuple[dict, Path]:
    """
    Load frozen requirements by jd_hash (primary key).
    Finds artifact matching *.<jd_hash>.v1.json.
    Returns (requirements_doc, artifact_path).
    FAILS (raises FileNotFoundError) if no artifact found. No silent regeneration.
    """
    pattern = f"*.{jd_hash}.v1.json"
    matches = list(ARTIFACTS_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"Requirements artifact not found for jd_hash={jd_hash[:16]}... "
            "Run POST /api/requirements/build first with the same JD. No automatic regeneration."
        )
    path = matches[0]
    return json.loads(path.read_text(encoding="utf-8")), path


def save_evidence_artifact(evidence_map: dict) -> Path:
    """Save evidence map for audit."""
    _ensure_artifacts_dir()
    run_id = evidence_map.get("run_id", "unknown")
    jd_hash = evidence_map.get("jd_hash", "unknown")[:16]
    resume_hash = evidence_map.get("resume_hash", "unknown")[:16]
    filename = f"evidence_{jd_hash}_{resume_hash}_{run_id}.json"
    path = ARTIFACTS_DIR / filename
    path.write_text(json.dumps(evidence_map, indent=2), encoding="utf-8")
    return path


def load_evidence_artifact(path: Path) -> dict:
    """Load evidence map from path."""
    return json.loads(path.read_text(encoding="utf-8"))
