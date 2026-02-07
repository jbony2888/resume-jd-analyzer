"""Stage B: Deterministic normalization — merge near-duplicates, stable IDs, category precedence."""

import hashlib
import re

EXTRACT_REQ_VERSION = "EXTRACT_REQ_V2"
MATCH_EVIDENCE_VERSION = "MATCH_EVIDENCE_V2"

# Category precedence: AI > Systems > Infrastructure > Technical > Domain > Collaboration > Behavioral
CATEGORY_PRECEDENCE = ["AI", "Systems", "Infrastructure", "Technical", "Domain", "Collaboration", "Behavioral"]
CATEGORY_KEYWORDS = {
    "AI": ["llm", "genai", "machine learning", "ml", "model", "inference", "prompt", "evaluation", "retrieval", "nlp"],
    "Systems": ["distributed", "scalability", "reliability", "services", "architecture", "microservices"],
    "Infrastructure": ["k8s", "kubernetes", "terraform", "ci/cd", "observability", "monitoring", "docker", "aws", "gcp"],
    "Technical": ["typescript", "python", "node", "react", "sql", "api", "fastapi", "django", "postgresql"],
    "Domain": ["healthcare", "fintech", "gov", "compliance", "mental health", "patient"],
    "Collaboration": ["cross-functional", "stakeholders", "clinicians", "product", "designers"],
    "Behavioral": ["ownership", "leadership", "mentoring", "communication", "mentorship"],
}
VALID_CATEGORIES = set(CATEGORY_PRECEDENCE)
JACCARD_THRESHOLD = 0.8


def _slugify(name: str) -> str:
    """Normalize: lowercase, trim, replace non-alnum with _, collapse underscores."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"


def _compute_requirement_key(req: dict) -> str:
    """Compute requirement_key from name if missing."""
    key = req.get("requirement_key") or ""
    key = _slugify(key) if key else _slugify(req.get("name", ""))
    return key or "unknown"


def _map_category(category: str, name: str, description: str) -> str:
    """Map to valid category using precedence and keyword matching."""
    cat = (category or "").strip()
    if cat in VALID_CATEGORIES:
        return cat
    combined = f"{name} {description}".lower()
    for c in CATEGORY_PRECEDENCE:
        for kw in CATEGORY_KEYWORDS.get(c, []):
            if kw in combined:
                return c
    return "Technical"


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two token sets."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _token_set(text: str) -> set[str]:
    """Tokenize for Jaccard: lowercase alphanumeric tokens."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return set(tokens)


def _stable_id(requirement_key: str, category: str, must_have: bool) -> str:
    """Stable ID: REQ- + first 10 chars of sha256(requirement_key|category|must_have)."""
    payload = f"{requirement_key}|{category}|{must_have}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"REQ-{h[:10]}"


def normalize_requirements(raw_requirements: list[dict]) -> list[dict]:
    """
    Deterministic normalization:
    - Compute requirement_key from name if missing
    - Enforce single category by precedence
    - Merge near-duplicates (same key or Jaccard >= 0.8)
    - Stable IDs from content hash
    - Sort: must_have desc, category precedence, requirement_key asc
    """
    if not raw_requirements:
        return []

    # Enrich with requirement_key and mapped category
    enriched = []
    for req in raw_requirements:
        name = (req.get("name") or "").strip()
        if not name:
            continue
        key = _compute_requirement_key(req)
        category = _map_category(
            req.get("category"),
            name,
            req.get("description", ""),
        )
        importance = req.get("importance", req.get("must_have", True))
        if isinstance(importance, str):
            must_have = "must" in importance.lower() or "required" in importance.lower()
        else:
            must_have = bool(importance)
        weight = req.get("weight", 3)
        if not isinstance(weight, int) or weight < 1 or weight > 5:
            weight = 3
        aliases = list(dict.fromkeys(req.get("aliases") or []))  # dedupe preserving order
        enriched.append({
            "name": name,
            "requirement_key": key,
            "category": category,
            "description": (req.get("description") or "").strip(),
            "must_have": must_have,
            "weight": weight,
            "aliases": aliases,
        })

    # Merge near-duplicates
    merged: list[dict] = []
    used_keys: set[str] = set()

    for curr in enriched:
        key = curr["requirement_key"]
        curr_tokens = _token_set(curr["name"]) | _token_set(curr["description"])

        found = False
        for m in merged:
            if key == m["requirement_key"]:
                # Same key: merge
                m["name"] = max(m["name"], curr["name"], key=len)
                m["aliases"] = list(dict.fromkeys(m["aliases"] + curr["aliases"]))
                m["must_have"] = m["must_have"] or curr["must_have"]
                found = True
                break
            # Jaccard overlap
            m_tokens = _token_set(m["name"]) | _token_set(m["description"])
            if _jaccard(curr_tokens, m_tokens) >= JACCARD_THRESHOLD:
                m["name"] = max(m["name"], curr["name"], key=len)
                m["aliases"] = list(dict.fromkeys(m["aliases"] + curr["aliases"]))
                m["must_have"] = m["must_have"] or curr["must_have"]
                found = True
                break

        if not found:
            merged.append(curr.copy())

    # Assign stable IDs and build output
    for m in merged:
        m["id"] = _stable_id(m["requirement_key"], m["category"], m["must_have"])

    # Sort: must_have desc, category precedence asc, requirement_key asc
    def sort_key(r):
        prec = CATEGORY_PRECEDENCE.index(r["category"]) if r["category"] in CATEGORY_PRECEDENCE else 99
        return (not r["must_have"], prec, r["requirement_key"])

    merged.sort(key=sort_key)

    return [
        {
            "id": r["id"],
            "requirement_key": r["requirement_key"],
            "category": r["category"],
            "name": r["name"],
            "description": r["description"],
            "must_have": r["must_have"],
            "weight": r["weight"],
            "aliases": r["aliases"],
        }
        for r in merged
    ]
