"""4-stage pipeline: extract → normalize → match → score."""

from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.artifacts import (
    save_requirements_artifact,
    load_requirements_artifact,
    save_evidence_artifact,
    load_evidence_artifact,
)
from src.pipeline.normalize import normalize_requirements
from src.pipeline.match import match_resume_to_requirements

__all__ = [
    "extract_requirements_from_jd",
    "normalize_requirements",
    "save_requirements_artifact",
    "load_requirements_artifact",
    "save_evidence_artifact",
    "load_evidence_artifact",
    "match_resume_to_requirements",
]
