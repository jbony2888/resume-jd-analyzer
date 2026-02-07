"""Stage A: Extract requirements from JD (LLM-assisted, offline)."""

import json
import os
from pathlib import Path

from groq import Groq

from src.utils import hash_text, iso_now
from src.pipeline.normalize import normalize_requirements, EXTRACT_REQ_VERSION

PROMPT_VERSION = EXTRACT_REQ_VERSION
REQUIREMENTS_VERSION = "2.0.0"
# Stage A: use stronger model for extraction (less drift); 8B increases variance
MODEL_ID = os.environ.get("GROQ_EXTRACT_MODEL") or os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile"
MODEL_PARAMS = {"temperature": 0, "top_p": 1}


def _load_prompt(name: str) -> str:
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")


def extract_requirements_from_jd(api_key: str, jd_text: str, role_id: str | None = None) -> dict:
    """
    Stage A: Extract requirements from JD using LLM.
    Returns full requirements doc with normalized, stable-IDs requirements.
    Retries once on invalid JSON; fails gracefully on second failure.
    """
    prompt_template = _load_prompt("extract_requirements")
    prompt = prompt_template.replace("{{jd_text}}", jd_text)
    prompt_hash = hash_text(prompt)

    client = Groq(api_key=api_key)

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "user", "content": prompt}],
                temperature=MODEL_PARAMS["temperature"],
                top_p=MODEL_PARAMS.get("top_p", 1),
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            break
        except json.JSONDecodeError as e:
            if attempt == 1:
                raise ValueError(f"Invalid JSON from model after retry: {e}") from e

    jd_hash = hash_text(jd_text)
    role_id = role_id or f"role_{jd_hash[:12]}"
    raw = data.get("requirements", [])
    requirements = normalize_requirements(raw)

    return {
        "role_id": role_id,
        "jd_hash": jd_hash,
        "requirements_version": REQUIREMENTS_VERSION,
        "created_at": iso_now(),
        "role_title": data.get("role_title", ""),
        "requirements": requirements,
        "_audit": {
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": prompt_hash,
            "model_id": MODEL_ID,
            "model_params": MODEL_PARAMS,
        },
    }
