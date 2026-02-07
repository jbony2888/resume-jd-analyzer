#!/usr/bin/env python3
"""
Run idempotency check: same (resume, JD) N times; output variance report if not identical.
Usage: python scripts/run_idempotency_check.py [--runs 10] [--jd path] [--resume path]
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import hash_text
from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact_by_jd_hash
from src.pipeline.match import match_resume_to_requirements
from src.scoring import compute_score

DEFAULT_RUNS = 10
DEFAULT_JD = "sample_jd.txt"
DEFAULT_RESUME = "resumes/master/Master-Copy-Resume.pdf"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--jd", default=DEFAULT_JD)
    parser.add_argument("--resume", default=DEFAULT_RESUME)
    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY required", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parent.parent
    jd_path = root / args.jd
    resume_path = root / args.resume

    if not jd_path.exists():
        print(f"Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)
    if not resume_path.exists():
        print(f"Error: Resume file not found: {resume_path}", file=sys.stderr)
        sys.exit(1)

    jd_text = jd_path.read_text(encoding="utf-8")
    if resume_path.suffix.lower() == ".pdf":
        from gap_analyzer import extract_text_from_pdf
        resume_text = extract_text_from_pdf(resume_path)
    else:
        resume_text = resume_path.read_text(encoding="utf-8")

    jd_hash = hash_text(jd_text)

    # Ensure artifact exists
    try:
        requirements_doc, _ = load_requirements_artifact_by_jd_hash(jd_hash)
    except FileNotFoundError:
        print("Creating requirements artifact...")
        doc = extract_requirements_from_jd(api_key, jd_text)
        to_save = {k: v for k, v in doc.items() if k != "_audit"}
        save_requirements_artifact(doc["role_id"], doc["jd_hash"], to_save)
        requirements_doc, _ = load_requirements_artifact_by_jd_hash(jd_hash)

    print(f"Running match+score {args.runs} times...")
    results = []
    for i in range(args.runs):
        evidence_map = match_resume_to_requirements(api_key, resume_text, requirements_doc)
        score = compute_score(requirements_doc, evidence_map)
        match_by_id = {m["requirement_id"]: m["matched"] for m in evidence_map["matches"]}
        results.append({
            "model_id": evidence_map.get("model_id"),
            "matched": match_by_id,
            "score": score["overall_score"],
            "total_matched": score["total_matched"],
        })

    # Variance check
    first = results[0]
    variances = []

    for i, r in enumerate(results[1:], start=1):
        if r["matched"] != first["matched"]:
            diff = {
                k: (r["matched"].get(k), first["matched"].get(k))
                for k in set(r["matched"]) | set(first["matched"])
                if r["matched"].get(k) != first["matched"].get(k)
            }
            variances.append(("match", i + 1, diff))
        if r["score"] != first["score"]:
            variances.append(("score", i + 1, f"{r['score']} != {first['score']}"))
        if r["total_matched"] != first["total_matched"]:
            variances.append(("total_matched", i + 1, f"{r['total_matched']} != {first['total_matched']}"))

    if variances:
        print("\n=== VARIANCE REPORT ===\n")
        for stage, run, detail in variances:
            print(f"Run {run} - {stage}: {detail}")
        print("\nIdempotency check FAILED.")
        sys.exit(1)
    else:
        print(f"\nIdempotency check PASSED: {args.runs} runs identical.")
        print(f"  model: {results[0].get('model_id', 'unknown')}")
        print(f"  num_requirements: {len(results[0]['matched'])}")
        print(f"  requirement_ids: {list(results[0]['matched'].keys())[:5]}...")
        print(f"  score: {first['score']}")
        print(f"  total_matched: {first['total_matched']}")


if __name__ == "__main__":
    main()
