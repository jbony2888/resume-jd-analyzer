#!/usr/bin/env python3
"""
Repeatability harness: run same resume+JD analysis N times; assert identical results.
Exits 0 if stable, 1 if unstable. Prints variance report on failure.
Prints provenance (jd_hash, resume_hash, requirements_artifact_path, requirements_hash) so you
can verify you're testing the same artifact as earlier runs.

Usage: python scripts/repeatability_check.py [--runs 10] [--jd path] [--resume path] [--model MODEL]

Note: Default --jd sample_jd.txt produces ~12 requirements. To test the 26-req AI Staff Engineer
artifact (jd_hash 784a9663fc2a35c2...), pass the path to the JD file used by the UI for that run.
Save that JD to e.g. jd_26req.txt, then: --jd jd_26req.txt --runs 10

To compare 8B vs 70B: run twice with --model llama-3.1-8b-instant and --model llama-3.3-70b-versatile.
Compare validated matched_count, score, and invalid_quote_count across runs.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import hash_text
from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact_by_jd_hash
from gap_analyzer.frozen_pipeline import run_frozen_analysis

DEFAULT_RUNS = 10
DEFAULT_JD = "sample_jd.txt"
DEFAULT_RESUME = "resumes/master/Master-Copy-Resume.pdf"
DEFAULT_MODEL = "llama-3.1-8b-instant"


def _load_resume_text(resume_path: Path) -> str:
    if resume_path.suffix.lower() == ".pdf":
        from gap_analyzer.pdf_parser import extract_text_from_pdf
        return extract_text_from_pdf(resume_path)
    return resume_path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--jd", default=DEFAULT_JD)
    parser.add_argument("--resume", default=DEFAULT_RESUME)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model override (sets GROQ_MATCH_MODEL)")
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
    resume_text = _load_resume_text(resume_path)

    os.environ["GROQ_MATCH_MODEL"] = args.model

    jd_hash = hash_text(jd_text)
    try:
        load_requirements_artifact_by_jd_hash(jd_hash)
    except FileNotFoundError:
        print("Creating requirements artifact...")
        doc = extract_requirements_from_jd(api_key, jd_text)
        to_save = {k: v for k, v in doc.items() if k != "_audit"}
        save_requirements_artifact(doc["role_id"], doc["jd_hash"], to_save)

    print(f"Running analyze {args.runs} times (model={args.model})...")
    results = []
    for i in range(args.runs):
        result = run_frozen_analysis(api_key, jd_text, resume_text)
        match_pairs = sorted(
            (m["requirement_id"], m["matched"])
            for m in result.get("_evidence_matches", [])
        )
        # Get match pairs from gap_report (we don't have direct access to evidence_map here)
        # run_frozen_analysis returns gap_report; we need requirement_id -> matched
        # The result doesn't expose raw matches. We need to get them from the pipeline.
        # run_frozen_analysis calls match + compute_score internally. The gap_report has
        # id and status (MATCH/MISSING/GAP). So matched = (status == "MATCH")
        gap_report = result.get("gap_report", [])
        match_pairs = sorted(
            (g["id"], g.get("status") == "MATCH")
            for g in gap_report
        )
        results.append({
            "match_score": result["match_score"],
            "num_requirements": result["num_requirements"],
            "matched_count_raw": result.get("matched_count_raw"),
            "matched_count_validated": result.get("matched_count_validated"),
            "invalid_quote_count": result.get("invalid_quote_count", 0),
            "requirement_ids": [p[0] for p in match_pairs],
            "match_pairs": match_pairs,
            "requirements_hash": result.get("requirements_hash"),
            "requirements_source": result.get("requirements_source"),
            "requirements_artifact_path": result.get("requirements_artifact_path"),
            "requirements_version": result.get("requirements_version"),
            "jd_hash": result.get("jd_hash"),
            "resume_hash": result.get("resume_hash"),
        })

    first = results[0]
    variances = []

    for i, r in enumerate(results[1:], start=1):
        run_num = i + 1
        if r["match_score"] != first["match_score"]:
            variances.append(("score", run_num, f"{r['match_score']} != {first['match_score']}"))
        if r["invalid_quote_count"] != first["invalid_quote_count"]:
            variances.append(
                ("invalid_quote_count", run_num, f"{r['invalid_quote_count']} != {first['invalid_quote_count']}")
            )
        if r["requirement_ids"] != first["requirement_ids"]:
            diff_ids = [
                rid for rid in set(r["requirement_ids"]) | set(first["requirement_ids"])
                if (r["requirement_ids"].count(rid) if rid in r["requirement_ids"] else 0)
                != (first["requirement_ids"].count(rid) if rid in first["requirement_ids"] else 0)
            ]
            variances.append(("requirement_ids", run_num, f"diff: {diff_ids[:5]}"))
        if r["match_pairs"] != first["match_pairs"]:
            diff_pairs = [
                (rid, r_m, f_m)
                for (rid, r_m), (_, f_m) in zip(r["match_pairs"], first["match_pairs"])
                if r_m != f_m
            ][:5]
            variances.append(("match_booleans", run_num, f"first diffs: {diff_pairs}"))

    if variances:
        scores = [x["match_score"] for x in results]
        print("\n=== VARIANCE REPORT ===\n")
        print(f"Runs: {args.runs} | Model: {args.model}")
        print(f"Score range: min={min(scores)}, max={max(scores)}")
        print()
        for stage, run, detail in variances:
            print(f"  Run {run} - {stage}: {detail}")
        print("\nRepeatability check FAILED.")
        sys.exit(1)
    else:
        print("\nPASS: Repeatability check passed.")
        print("\n--- Provenance (verify same artifact as 26-req runs) ---")
        print(f"  jd_hash: {first.get('jd_hash', 'N/A')}")
        print(f"  resume_hash: {first.get('resume_hash', 'N/A')}")
        print(f"  requirements_source: {first.get('requirements_source', 'N/A')}")
        print(f"  requirements_artifact_path: {first.get('requirements_artifact_path', 'N/A')}")
        print(f"  requirements_hash: {first.get('requirements_hash', 'N/A')}")
        print(f"  requirements_version: {first.get('requirements_version', 'N/A')}")
        print("\n--- Run metrics ---")
        print(f"  model: {args.model}")
        print(f"  runs: {args.runs}")
        print(f"  match_score: {first['match_score']}")
        print(f"  num_requirements: {first['num_requirements']}")
        print(f"  matched_count_raw: {first.get('matched_count_raw', 'N/A')}")
        print(f"  matched_count_validated: {first.get('matched_count_validated', 'N/A')}")
        print(f"  invalid_quote_count: {first.get('invalid_quote_count', 0)}")
        if first.get("matched_count_raw") is not None and first.get("matched_count_validated") is not None:
            raw, val = first["matched_count_raw"], first["matched_count_validated"]
            delta = raw - val if raw is not None and val is not None else 0
            print(f"  raw_vs_validated_delta: {delta} (0 = healthy, >0 = guardrails caught invalid quotes)")
        print(f"  requirement_ids (first 5): {first['requirement_ids'][:5]}...")
        sys.exit(0)


if __name__ == "__main__":
    main()
