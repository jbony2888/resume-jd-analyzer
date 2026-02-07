"""Requirement freeze test: evaluation must fail if requirements artifact missing."""

import pytest

from src.pipeline.artifacts import load_requirements_artifact


def test_load_requirements_artifact_missing_raises():
    """load_requirements_artifact raises FileNotFoundError when artifact does not exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_requirements_artifact("nonexistent_role", "a" * 64)

    assert "Requirements artifact not found" in str(exc_info.value)
    assert "No automatic regeneration" in str(exc_info.value)
