"""Stage D: Deterministic scoring engine. Pure code, no LLM."""

from src.scoring.quote_validation import validate_evidence_quotes


class EvidenceRequiredError(ValueError):
    """Raised when matched=true but evidence array is empty."""


def validate_evidence_map(
    requirements_doc: dict, evidence_map: dict, resume_text: str | None = None
) -> None:
    """
    Validate evidence map: matched=true MUST have evidence.
    If resume_text provided, re-validate quotes (safety net).
    Raises EvidenceRequiredError if invalid.
    """
    if resume_text:
        validate_evidence_quotes(resume_text, evidence_map, min_len=12)

    for m in evidence_map.get("matches", []):
        if m.get("matched") is True:
            evidence = m.get("evidence") or []
            if not evidence or not any(e.get("quote") for e in evidence):
                raise EvidenceRequiredError(
                    f"Requirement {m.get('requirement_id')} has matched=true but no evidence quote"
                )


def compute_score(
    requirements_doc: dict, evidence_map: dict, resume_text: str | None = None
) -> dict:
    """
    Stage D: Deterministic scoring from frozen requirements + evidence map.
    Returns category breakdown and totals.
    """
    validate_evidence_map(requirements_doc, evidence_map, resume_text)

    requirements = requirements_doc.get("requirements", [])
    match_by_id = {m["requirement_id"]: m for m in evidence_map.get("matches", [])}

    must_have = [r for r in requirements if r.get("must_have")]
    nice_to_have = [r for r in requirements if not r.get("must_have")]

    must_have_matched = sum(1 for r in must_have if match_by_id.get(r["id"], {}).get("matched"))
    nice_to_have_matched = sum(1 for r in nice_to_have if match_by_id.get(r["id"], {}).get("matched"))

    must_have_coverage = (must_have_matched / len(must_have) * 100) if must_have else 100.0
    nice_to_have_coverage = (nice_to_have_matched / len(nice_to_have) * 100) if nice_to_have else 100.0

    # Per-category scores
    categories: dict[str, list] = {}
    for r in requirements:
        cat = r.get("category", "Technical")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    per_category = {}
    for cat, reqs in categories.items():
        matched = sum(1 for r in reqs if match_by_id.get(r["id"], {}).get("matched"))
        total = len(reqs)
        per_category[cat] = {
            "matched": matched,
            "total": total,
            "pct": round(matched / total * 100, 1) if total else 0,
        }

    total_reqs = len(requirements)
    total_matched = sum(1 for r in requirements if match_by_id.get(r["id"], {}).get("matched"))
    overall_score = round(total_matched / total_reqs * 100, 1) if total_reqs else 0

    return {
        "must_have_coverage": round(must_have_coverage, 1),
        "nice_to_have_coverage": round(nice_to_have_coverage, 1),
        "must_have_matched": must_have_matched,
        "must_have_total": len(must_have),
        "nice_to_have_matched": nice_to_have_matched,
        "nice_to_have_total": len(nice_to_have),
        "per_category_scores": per_category,
        "overall_score": overall_score,
        "total_matched": total_matched,
        "total_requirements": total_reqs,
    }
