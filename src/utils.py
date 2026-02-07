"""Utilities for hashing and audit metadata."""

import hashlib
from datetime import datetime, timezone


def hash_text(text: str) -> str:
    """Compute SHA256 hash of text. Deterministic."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iso_now() -> str:
    """Current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
