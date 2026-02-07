"""Stage C: Match resume to requirements (LLM-assisted evidence extraction)."""

import json
import os
import uuid
from pathlib import Path

from groq import Groq

from src.utils import hash_text
from src.pipeline.normalize import MATCH_EVIDENCE_VERSION
from src.scoring.quote_validation import validate_evidence_quotes

PROMPT_VERSION = MATCH_EVIDENCE_VERSION
# Stage C: 8B is fine for evidence matching (string search + quoting)
MODEL_ID = os.environ.get("GROQ_MATCH_MODEL") or os.environ.get("GROQ_MODEL") or "llama-3.1-8b-instant"
MODEL_PARAMS = {"temperature": 0, "top_p": 1}


def _load_prompt(name: str) -> str:
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")


def _strip_confidence(matches: list[dict]) -> list[dict]:
    """Remove confidence for determinism; matched is authoritative."""
    return [{k: v for k, v in m.items() if k != "confidence"} for m in matches]


def _sanitize_notes(matches: list[dict]) -> None:
    """Coerce None notes to empty string (schema expects string)."""
    for m in matches:
        if m.get("notes") is None:
            m["notes"] = ""


def match_resume_to_requirements(
    api_key: str,
    resume_text: str,
    requirements_doc: dict,
) -> dict:
    """
    Stage C: LLM-assisted evidence matching.
    Returns evidence map. Does NOT compute scores.
    Retries once on invalid JSON; fails gracefully on second failure.
    """
    requirements = requirements_doc.get("requirements", [])
    # Do NOT include description (JD-derived) - prevents model from echoing JD as evidence
    reqs_for_prompt = [
        {
            "id": r["id"],
            "requirement_key": r.get("requirement_key", ""),
            "name": r["name"],
            "aliases": r.get("aliases", []),
        }
        for r in requirements
    ]
    reqs_json = json.dumps(reqs_for_prompt)

    prompt_template = _load_prompt("match_evidence")
    prompt = prompt_template.replace("{{requirements_json}}", reqs_json).replace("{{resume_text}}", resume_text)
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

    matches = _strip_confidence(data.get("matches", []))
    _sanitize_notes(matches)

    # Map back to our requirement IDs (LLM may return by id or requirement_key)
    req_by_id = {r["id"]: r for r in requirements}
    req_by_key = {r.get("requirement_key", ""): r for r in requirements}
    normalized_matches = []
    for m in matches:
        rid = m.get("requirement_id")
        rkey = m.get("requirement_key", "")
        req = req_by_id.get(rid) or req_by_key.get(rkey)
        if req:
            normalized_matches.append({
                "requirement_id": req["id"],
                "requirement_key": req.get("requirement_key", ""),
                "matched": m.get("matched", False),
                "evidence": m.get("evidence", []),
                "notes": (m.get("notes") or ""),
            })
        else:
            normalized_matches.append(m)

    resume_hash = hash_text(resume_text)
    run_id = str(uuid.uuid4())[:8]

    evidence_map = {
        "role_id": requirements_doc.get("role_id", ""),
        "jd_hash": requirements_doc.get("jd_hash", ""),
        "resume_hash": resume_hash,
        "requirements_version": requirements_doc.get("requirements_version", ""),
        "prompt_version": PROMPT_VERSION,
        "model_id": MODEL_ID,
        "run_id": run_id,
        "matches": normalized_matches,
        "_audit": {
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": prompt_hash,
            "model_id": MODEL_ID,
            "model_params": MODEL_PARAMS,
        },
    }

    # Hard quote validation: invalid quotes -> matched=false, evidence cleared
    evidence_map = validate_evidence_quotes(resume_text, evidence_map, min_len=12)
    meta = evidence_map.get("meta", {})
    evidence_map["_audit"]["matched_count_raw"] = meta.get("matched_count_raw")
    evidence_map["_audit"]["matched_count_validated"] = meta.get("matched_count_validated")
    evidence_map["_audit"]["invalid_quote_count"] = meta.get("invalid_quote_count")
    evidence_map["_audit"]["evidence_prompt_includes_description"] = False

    return evidence_map
