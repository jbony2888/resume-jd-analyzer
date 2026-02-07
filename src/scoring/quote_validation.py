"""Hard quote validation: evidence quotes must be verbatim substrings of resume text."""

import re


def normalize_text(s: str) -> str:
    """Collapse all whitespace to single spaces, strip ends."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip())


def validate_evidence_quotes(
    resume_text: str, evidence_map: dict, min_len: int = 12
) -> dict:
    """
    Validate every evidence quote is a verbatim substring of resume text.
    If any quote is invalid: set matched=false, clear evidence, set invalid_quote=True.
    Mutates evidence_map in place and adds meta with stats.
    Returns evidence_map (mutated).
    """
    matches = evidence_map.get("matches", [])
    resume_norm = normalize_text(resume_text)
    invalid_quote_count = 0
    matched_count_raw = sum(1 for m in matches if m.get("matched") is True)

    for m in matches:
        if m.get("matched") is not True:
            m["invalid_quote"] = False
            continue

        evidence = m.get("evidence") or []
        quotes = [e.get("quote", "") for e in evidence if e.get("quote")]

        if not quotes:
            m["invalid_quote"] = False
            continue

        any_invalid = False
        for q in quotes:
            qn = normalize_text(q)
            if len(qn) < min_len or qn not in resume_norm:
                any_invalid = True
                break

        if any_invalid:
            m["matched"] = False
            m["evidence"] = []
            m["invalid_quote"] = True
            invalid_quote_count += 1
        else:
            m["invalid_quote"] = False

    matched_count_validated = sum(1 for m in matches if m.get("matched") is True)
    evidence_map["meta"] = {
        "invalid_quote_count": invalid_quote_count,
        "matched_count_raw": matched_count_raw,
        "matched_count_validated": matched_count_validated,
        "evidence_prompt_includes_description": False,
    }
    return evidence_map
