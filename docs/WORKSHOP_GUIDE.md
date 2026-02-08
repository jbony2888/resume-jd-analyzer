# Resume-Job Description Gap Analyzer
# Live Workshop Guide — 4 Modules (2 Hours)

---

## Workshop Overview

**Duration:** 2 hours  
**Audience:** Coding beginners  
**Goal:** Build an AI-powered tool that compares a resume to a job description and produces a structured, auditable score. 

### Pipeline Flow

```
Job Description → [Module 1: Extract] → Requirements (stored locally)
Resume          → [Module 2: Match]  → Evidence Map
                → [Module 3: Score]  → Final Score %
                → [Module 4: Integrate] → CLI + Local persistence
```

---

## Quick Setup (10 min)

### Create project & environment

```bash
mkdir resume-jd-analyzer
cd resume-jd-analyzer
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### Install dependencies

Create `requirements.txt`:

```
groq>=0.4.0
pypdf>=4.0.0
python-dotenv>=1.0.0
```

```bash
pip install -r requirements.txt
```

### API key

1. Sign up at [console.groq.com](https://console.groq.com)
2. Create `.env` with: `GROQ_API_KEY=gsk_your_key_here`

### Project structure

Create these folders and empty `__init__.py` files: `src/`, `src/pipeline/`, `src/scoring/`. (Each `__init__.py` can be empty—Python uses them to recognize packages.)

### Shared helpers (pre-built)

Create `src/utils.py`:

```python
"""Utilities for hashing and audit metadata."""
import hashlib
from datetime import datetime, timezone

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
```

Create `gap_analyzer/__init__.py`:

```python
from gap_analyzer.pdf_parser import extract_text_from_pdf
__all__ = ["extract_text_from_pdf"]
```

Create `gap_analyzer/pdf_parser.py`:

```python
from pathlib import Path
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(path)
    text_parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_parts.append(t)
    return "\n\n".join(text_parts).strip()
```

---

## Module 1: Requirements Extractor (30 min)

### What this module does (beginner explanation)

A job description is free-form text: bullet points, paragraphs, and sentences. A computer can’t directly compare that to a resume—it needs a **structured list** of skills and requirements.

**This module turns a messy job description into a clean checklist.** Think of it like: you read a job ad and write down a list of items such as "Python 3," "Docker," "5+ years experience." The AI does that for you: it reads the JD, identifies each requirement, labels it (e.g., must-have vs nice-to-have), and gives each one a stable ID.

**Why we need it:** Later, when we match resumes, we compare against this exact list. Having a structured, normalized list makes the rest of the pipeline consistent and reproducible.

**When to use it:** Whenever a new job is posted—you run this once per job, then reuse the result for every resume you evaluate.

### 1.1 Prompt

Create `prompts/extract_requirements.txt`:

```
You are an expert HR analyst. Extract structured requirements from the Job Description.

RULES:
- EXTRACT ONLY explicit requirements. Assign ONE category: AI, Systems, Infrastructure, Technical, Domain, Collaboration, or Behavioral.
- Set must_have=true for "required", "must have". Set must_have=false for "nice to have", "preferred".
- Assign weight 1-5 (5=most critical). Include aliases (e.g. "Python" → ["Python 3", "Python3"]).
- requirement_key: slugified name (lowercase, alphanumeric + underscores).

OUTPUT: Strictly valid JSON. No other text.
{
  "role_title": "string",
  "requirements": [
    {
      "id": "REQ-0000000000",
      "requirement_key": "python_3",
      "category": "Technical",
      "name": "string",
      "description": "string",
      "must_have": true,
      "weight": 1-5,
      "aliases": ["string"]
    }
  ]
}

Job Description:
---
{{jd_text}}
---
```

### 1.2 Normalize

Create `src/pipeline/normalize.py`:

```python
"""Deterministic normalization — stable IDs, dedupe."""
import hashlib
import re

CATEGORY_PRECEDENCE = ["AI", "Systems", "Infrastructure", "Technical", "Domain", "Collaboration", "Behavioral"]
VALID_CATEGORIES = set(CATEGORY_PRECEDENCE)

def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"

def _stable_id(requirement_key: str, category: str, must_have: bool) -> str:
    payload = f"{requirement_key}|{category}|{must_have}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"REQ-{h[:10]}"

def normalize_requirements(raw_requirements: list[dict]) -> list[dict]:
    if not raw_requirements:
        return []
    result = []
    seen_keys = set()
    for req in raw_requirements:
        name = (req.get("name") or "").strip()
        if not name:
            continue
        key = _slugify(req.get("requirement_key") or name)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        category = (req.get("category") or "Technical").strip()
        if category not in VALID_CATEGORIES:
            category = "Technical"
        importance = req.get("importance", req.get("must_have", True))
        if isinstance(importance, str):
            must_have = "must" in importance.lower() or "required" in importance.lower()
        else:
            must_have = bool(importance)
        weight = req.get("weight", 3)
        if not isinstance(weight, int) or weight < 1 or weight > 5:
            weight = 3
        result.append({
            "id": _stable_id(key, category, must_have),
            "requirement_key": key,
            "category": category,
            "name": name,
            "description": (req.get("description") or "").strip(),
            "must_have": must_have,
            "weight": weight,
            "aliases": list(dict.fromkeys(req.get("aliases") or [])),
        })
    return result
```

### 1.3 Extract

Create `src/pipeline/extract.py`:

```python
"""Extract requirements from JD (LLM-assisted)."""
import json
from pathlib import Path
from groq import Groq
from src.utils import hash_text, iso_now
from src.pipeline.normalize import normalize_requirements

MODEL_ID = "llama-3.3-70b-versatile"

def _load_prompt(name: str) -> str:
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")

def extract_requirements_from_jd(api_key: str, jd_text: str, role_id: str | None = None) -> dict:
    prompt = _load_prompt("extract_requirements").replace("{{jd_text}}", jd_text)
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        top_p=1,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content.strip())
    jd_hash = hash_text(jd_text)
    role_id = role_id or f"role_{jd_hash[:12]}"
    return {
        "role_id": role_id,
        "jd_hash": jd_hash,
        "requirements_version": "2.0.0",
        "created_at": iso_now(),
        "role_title": data.get("role_title", ""),
        "requirements": normalize_requirements(data.get("requirements", [])),
    }
```

---

## Module 2: Evidence Matcher (30 min)

### What this module does (beginner explanation)

We now have a checklist of requirements from the job description. Next we need to answer: **Does this resume prove they meet each requirement?**

**This module goes through each requirement and looks for proof in the resume.** For example, if the job asks for "Python 3," the AI searches the resume for mentions of Python and, when it finds one, records the exact quote (e.g., "Built APIs in Python 3.10"). That quote is the **evidence**.

**Why we need evidence:** Anyone could claim "yes, matched." Evidence means we can point to the exact sentence in the resume that supports the match. We also validate that every quote really appears in the resume—no making things up.

**When to use it:** Every time a candidate submits a resume. You load the saved requirements for that job, then run this module to produce an evidence map.

### 2.1 Prompt

Create `prompts/match_evidence.txt`:

```
You are an evidence matcher. For each requirement, find PROVEN evidence in the Resume text ONLY.

CRITICAL:
- ONLY quote from the Resume. Do NOT quote from Requirements.
- matched=true ONLY if you find a verbatim quote. matched=false otherwise, evidence=[].
- For matched=true, evidence MUST have at least one item with "quote" (exact substring from resume).
- Do NOT fabricate evidence.

Requirements:
{{requirements_json}}

Resume text:
---
{{resume_text}}
---

Return JSON:
{
  "matches": [
    {
      "requirement_id": "REQ-xxx",
      "requirement_key": "python_3",
      "matched": true,
      "evidence": [{"quote": "exact substring from resume"}],
      "notes": ""
    }
  ]
}
```

### 2.2 Quote validation

Create `src/scoring/quote_validation.py`:

```python
"""Validate evidence quotes are verbatim substrings of resume."""
import re

def normalize_text(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip())

def validate_evidence_quotes(resume_text: str, evidence_map: dict, min_len: int = 12) -> dict:
    matches = evidence_map.get("matches", [])
    resume_norm = normalize_text(resume_text)
    for m in matches:
        if m.get("matched") is not True:
            continue
        quotes = [e.get("quote", "") for e in (m.get("evidence") or []) if e.get("quote")]
        if not quotes:
            continue
        any_invalid = any(len(normalize_text(q)) < min_len or normalize_text(q) not in resume_norm for q in quotes)
        if any_invalid:
            m["matched"] = False
            m["evidence"] = []
    return evidence_map
```

### 2.3 Match

Create `src/pipeline/match.py`:

```python
"""Match resume to requirements (LLM-assisted evidence extraction)."""
import json
import uuid
from pathlib import Path
from groq import Groq
from src.utils import hash_text
from src.scoring.quote_validation import validate_evidence_quotes

MODEL_ID = "llama-3.1-8b-instant"

def _load_prompt(name: str) -> str:
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")

def match_resume_to_requirements(api_key: str, resume_text: str, requirements_doc: dict) -> dict:
    requirements = requirements_doc.get("requirements", [])
    reqs_for_prompt = [{"id": r["id"], "requirement_key": r.get("requirement_key", ""), "name": r["name"], "aliases": r.get("aliases", [])} for r in requirements]
    prompt = _load_prompt("match_evidence").replace("{{requirements_json}}", json.dumps(reqs_for_prompt)).replace("{{resume_text}}", resume_text)
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(model=MODEL_ID, messages=[{"role": "user", "content": prompt}], temperature=0, top_p=1, response_format={"type": "json_object"})
    data = json.loads(response.choices[0].message.content.strip())
    matches = data.get("matches", [])
    req_by_id = {r["id"]: r for r in requirements}
    req_by_key = {r.get("requirement_key", ""): r for r in requirements}
    normalized = []
    for m in matches:
        req = req_by_id.get(m.get("requirement_id")) or req_by_key.get(m.get("requirement_key", ""))
        if req:
            normalized.append({"requirement_id": req["id"], "requirement_key": req.get("requirement_key", ""), "matched": m.get("matched", False), "evidence": m.get("evidence", []), "notes": (m.get("notes") or "")})
    evidence_map = {"role_id": requirements_doc.get("role_id", ""), "jd_hash": requirements_doc.get("jd_hash", ""), "resume_hash": hash_text(resume_text), "requirements_version": requirements_doc.get("requirements_version", ""), "model_id": MODEL_ID, "run_id": str(uuid.uuid4())[:8], "matches": normalized}
    return validate_evidence_quotes(resume_text, evidence_map, min_len=12)
```

---

## Module 3: Scoring Engine (30 min)

### What this module does (beginner explanation)

By now we have: (1) a list of requirements, and (2) for each requirement, whether the resume matched and what evidence it provided. **We still need a single number—a score—to show how well the resume fits the job.**

**This module does simple math.** It counts how many requirements were matched, splits them into must-have vs nice-to-have, and computes percentages. For example: "8 out of 10 must-haves matched (80%), 3 out of 5 nice-to-haves matched (60%), overall 73%."

**Why it's pure code (no AI here):** The hard work—extracting requirements and finding evidence—is already done. Scoring is just counting and dividing. Using code instead of an LLM keeps it fast, predictable, and auditable. Same inputs always give the same score.

**When to use it:** Right after the Evidence Matcher. You pass in the requirements and the evidence map, and you get back the score breakdown.

### 3.1 Engine

Create `src/scoring/engine.py`:

```python
"""Deterministic scoring engine. Pure code, no LLM."""

def compute_score(requirements_doc: dict, evidence_map: dict) -> dict:
    requirements = requirements_doc.get("requirements", [])
    match_by_id = {m["requirement_id"]: m for m in evidence_map.get("matches", [])}
    must_have = [r for r in requirements if r.get("must_have")]
    nice_to_have = [r for r in requirements if not r.get("must_have")]
    must_have_matched = sum(1 for r in must_have if match_by_id.get(r["id"], {}).get("matched"))
    nice_to_have_matched = sum(1 for r in nice_to_have if match_by_id.get(r["id"], {}).get("matched"))
    must_have_coverage = (must_have_matched / len(must_have) * 100) if must_have else 100.0
    nice_to_have_coverage = (nice_to_have_matched / len(nice_to_have) * 100) if nice_to_have else 100.0
    total_reqs = len(requirements)
    total_matched = sum(1 for r in requirements if match_by_id.get(r["id"], {}).get("matched"))
    overall_score = round(total_matched / total_reqs * 100, 1) if total_reqs else 0
    return {
        "must_have_coverage": round(must_have_coverage, 1),
        "nice_to_have_coverage": round(nice_to_have_coverage, 1),
        "overall_score": overall_score,
        "total_matched": total_matched,
        "total_requirements": total_reqs,
    }
```

Create `src/scoring/__init__.py`:

```python
from src.scoring.engine import compute_score
__all__ = ["compute_score"]
```

---

## Module 4: Integration & Persistence (30 min)

### What this module does (beginner explanation)

Modules 1–3 do the core work, but they need to be **wired together** and **saved somewhere**. Otherwise you’d have to re-extract requirements every time and couldn’t reuse or audit results.

**This module does two things:**

1. **Persistence (saving to disk):** We save the requirements and evidence as JSON files in an `artifacts/` folder on your machine. That way, when you evaluate a resume tomorrow, we can load the same requirements instead of calling the AI again. All storage is local—no database or cloud.

2. **Integration (the CLI):** We connect all the modules into one program you can run from the terminal. You type commands like `create-requirements sample_jd.txt` and `evaluate resume.pdf`; the CLI calls the right module at the right time.

**Why we need it:** Without persistence, we’d lose our work. Without the CLI (or similar integration), you’d have to write custom scripts every time. This module ties everything into a usable tool.

### 4.1 Local storage

Create `src/pipeline/artifacts.py`:

```python
"""Local artifact storage — requirements and evidence saved as JSON files on disk."""

import json
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"

def _ensure_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR

def save_requirements_artifact(role_id: str, jd_hash: str, requirements_doc: dict) -> Path:
    _ensure_dir()
    safe_role = "".join(c if c.isalnum() or c in "-_" else "_" for c in role_id)
    path = ARTIFACTS_DIR / f"job_requirements.{safe_role}.{jd_hash}.v1.json"
    path.write_text(json.dumps(requirements_doc, indent=2), encoding="utf-8")
    return path

def load_requirements_artifact(role_id: str, jd_hash: str) -> dict:
    safe_role = "".join(c if c.isalnum() or c in "-_" else "_" for c in role_id)
    path = ARTIFACTS_DIR / f"job_requirements.{safe_role}.{jd_hash}.v1.json"
    if not path.exists():
        raise FileNotFoundError(f"Requirements not found: {path}. Run create-requirements first.")
    return json.loads(path.read_text(encoding="utf-8"))

def save_evidence_artifact(evidence_map: dict) -> Path:
    _ensure_dir()
    run_id = evidence_map.get("run_id", "unknown")
    jd_hash = evidence_map.get("jd_hash", "unknown")[:16]
    resume_hash = evidence_map.get("resume_hash", "unknown")[:16]
    path = ARTIFACTS_DIR / f"evidence_{jd_hash}_{resume_hash}_{run_id}.json"
    path.write_text(json.dumps(evidence_map, indent=2), encoding="utf-8")
    return path
```

### 4.2 CLI

Create `cli_pipeline.py`:

```python
#!/usr/bin/env python3
"""CLI for resume-JD gap analyzer. Data stored locally in artifacts/."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gap_analyzer import extract_text_from_pdf
from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact, save_evidence_artifact
from src.pipeline.match import match_resume_to_requirements
from src.scoring import compute_score
from src.utils import hash_text

API_KEY = os.environ.get("GROQ_API_KEY")

def cmd_create(args):
    jd_text = Path(args.jd_file).read_text(encoding="utf-8")
    role_id = args.role_id or f"role_{hash_text(jd_text)[:12]}"
    doc = extract_requirements_from_jd(API_KEY, jd_text, role_id)
    path = save_requirements_artifact(role_id, doc["jd_hash"], doc)
    print(f"Saved: {path}")
    print(f"  role_id: {role_id}")
    print(f"  jd_hash: {doc['jd_hash']}")

def cmd_evaluate(args):
    resume_path = Path(args.resume)
    resume_text = extract_text_from_pdf(resume_path) if resume_path.suffix.lower() == ".pdf" else resume_path.read_text(encoding="utf-8")
    requirements_doc = load_requirements_artifact(args.role_id, args.jd_hash)
    evidence_map = match_resume_to_requirements(API_KEY, resume_text, requirements_doc)
    score_result = compute_score(requirements_doc, evidence_map)
    save_evidence_artifact(evidence_map)
    if args.json:
        print(json.dumps({"score": score_result}, indent=2))
    else:
        print("=== Score ===")
        print(f"Overall: {score_result['overall_score']}%")
        print(f"Must-have: {score_result['must_have_coverage']}%")
        print(f"Nice-to-have: {score_result['nice_to_have_coverage']}%")

def main():
    parser = argparse.ArgumentParser(description="Resume-JD Gap Analyzer")
    sub = parser.add_subparsers(dest="command", required=True)
    p1 = sub.add_parser("create-requirements")
    p1.add_argument("jd_file", type=Path)
    p1.add_argument("--role-id")
    p1.set_defaults(func=cmd_create)
    p2 = sub.add_parser("evaluate")
    p2.add_argument("resume", type=Path)
    p2.add_argument("--role-id", required=True)
    p2.add_argument("--jd-hash", required=True)
    p2.add_argument("--json", action="store_true")
    p2.set_defaults(func=cmd_evaluate)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
```

---

## Run the Pipeline

### Sample JD

Create `sample_jd.txt`:

```
Senior Python Developer

Requirements:
- Strong proficiency in Python 3.x
- Experience with FastAPI or Django
- Knowledge of PostgreSQL and Redis
- Experience with Docker and Kubernetes
- Cloud experience (AWS or GCP)

Nice to have:
- Experience with LLM APIs
- Knowledge of Terraform
```

### Commands

```bash
# 1. Extract requirements (save to artifacts/ locally)
python cli_pipeline.py create-requirements sample_jd.txt

# 2. Evaluate resume (use role_id and jd_hash from step 1)
python cli_pipeline.py evaluate resume.pdf --role-id <role_id> --jd-hash <jd_hash>

# JSON output
python cli_pipeline.py evaluate resume.pdf --role-id <role_id> --jd-hash <jd_hash> --json
```

---

## Concepts Glossary

| Term | Meaning |
|------|---------|
| **API** | Way for programs to call external services (e.g. Groq) |
| **LLM** | AI that processes text; we use Llama 3 via Groq |
| **Deterministic** | Same inputs → same outputs (important for fair scoring) |
| **JSON** | Text format for structured data |
| **Hash** | Fixed string from text; same text → same hash (identifiers) |
| **Local persistence** | Saving files (JSON) to disk on the user's machine |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `GROQ_API_KEY` missing | Set in `.env` |
| `FileNotFoundError` for requirements | Run `create-requirements` before `evaluate` |
| Import errors | Run from project root |
| Empty PDF text | Use text-based PDF or add OCR for scanned docs |

---

## Module Summary

| Module | Deliverables | Time |
|--------|--------------|------|
| 1. Requirements Extractor | `extract.py`, `normalize.py`, `extract_requirements.txt` | 30 min |
| 2. Evidence Matcher | `match.py`, `quote_validation.py`, `match_evidence.txt` | 30 min |
| 3. Scoring Engine | `engine.py` | 30 min |
| 4. Integration & Persistence | `artifacts.py`, `cli_pipeline.py` | 30 min |
