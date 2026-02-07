"""Schema validation for requirements and evidence maps."""

import json
from pathlib import Path

import jsonschema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_requirements(data: dict) -> None:
    """Validate job requirements against schema. Raises jsonschema.ValidationError if invalid."""
    schema = _load_schema("job_requirements")
    jsonschema.validate(data, schema)


def validate_evidence_map(data: dict) -> None:
    """Validate evidence map against schema. Raises jsonschema.ValidationError if invalid."""
    schema = _load_schema("evidence_map")
    jsonschema.validate(data, schema)
