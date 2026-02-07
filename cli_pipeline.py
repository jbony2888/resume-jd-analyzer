#!/usr/bin/env python3
"""CLI for deterministic resume-to-job matching pipeline."""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gap_analyzer import extract_text_from_pdf
from src.pipeline.extract import extract_requirements_from_jd
from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact, save_evidence_artifact
from src.pipeline.match import match_resume_to_requirements
from src.scoring import compute_score
from src.utils import hash_text
from src.validation import validate_evidence_map as validate_evidence_map_schema
from src.run_report import write_run_report


def _get_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        print("Error: GROQ_API_KEY required. Set in .env or pass --api-key", file=sys.stderr)
        sys.exit(1)
    return key


def cmd_create_requirements(args: argparse.Namespace) -> None:
    """Stage A+B: Extract from JD, normalize, save artifact."""
    api_key = _get_api_key(args.api_key)
    jd_path = Path(args.jd_file)
    if not jd_path.exists():
        print(f"Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)
    jd_text = jd_path.read_text(encoding="utf-8")
    role_id = args.role_id or f"role_{hash_text(jd_text)[:12]}"

    requirements_doc = extract_requirements_from_jd(api_key, jd_text, role_id)
    path = save_requirements_artifact(role_id, requirements_doc["jd_hash"], requirements_doc)
    print(f"Requirements artifact saved: {path}")
    print(f"  role_id: {role_id}")
    print(f"  jd_hash: {requirements_doc['jd_hash']}")
    print(f"  requirements_count: {len(requirements_doc['requirements'])}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Stage C+D: Load frozen requirements, match resume, deterministic score."""
    api_key = _get_api_key(args.api_key)
    resume_path = Path(args.resume)
    if not resume_path.exists():
        print(f"Error: Resume not found: {resume_path}", file=sys.stderr)
        sys.exit(1)

    # Extract resume text
    if resume_path.suffix.lower() == ".pdf":
        resume_text = extract_text_from_pdf(resume_path)
    else:
        resume_text = resume_path.read_text(encoding="utf-8")

    role_id = args.role_id
    jd_hash = args.jd_hash
    if not role_id or not jd_hash:
        print("Error: --role-id and --jd-hash required for evaluation. Use values from create-requirements.", file=sys.stderr)
        sys.exit(1)

    requirements_doc = load_requirements_artifact(role_id, jd_hash)
    evidence_map = match_resume_to_requirements(api_key, resume_text, requirements_doc)
    validate_evidence_map_schema(evidence_map)
    run_id = evidence_map.get("run_id", str(uuid.uuid4())[:8])

    score_result = compute_score(requirements_doc, evidence_map)
    total_reqs = len(requirements_doc["requirements"])
    total_matched = score_result["total_matched"]

    # Save evidence artifact
    save_evidence_artifact(evidence_map)

    # Write run report
    reports_dir = Path(args.reports_dir)
    report_path = reports_dir / f"run_report_{run_id}.json"
    write_run_report(
        report_path,
        role_id=role_id,
        jd_hash=jd_hash,
        resume_hash=evidence_map["resume_hash"],
        requirements_version=evidence_map["requirements_version"],
        prompt_version=evidence_map["prompt_version"],
        model_id=evidence_map["model_id"],
        run_id=run_id,
        score_result=score_result,
        total_requirements=total_reqs,
        total_matched=total_matched,
    )
    print(f"Run report: {report_path}")

    # Output
    if args.json:
        out = {
            "score": score_result,
            "evidence_map": {k: v for k, v in evidence_map.items() if k != "matches"},
            "matches_count": len(evidence_map.get("matches", [])),
        }
        print(json.dumps(out, indent=2))
    else:
        print("=== Score ===")
        print(f"Overall: {score_result['overall_score']}%")
        print(f"Must-have coverage: {score_result['must_have_coverage']}%")
        print(f"Nice-to-have coverage: {score_result['nice_to_have_coverage']}%")
        print("\nPer category:")
        for cat, d in score_result["per_category_scores"].items():
            print(f"  {cat}: {d['matched']}/{d['total']} ({d['pct']}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic resume-to-job matching pipeline")
    parser.add_argument("--api-key", help="Groq API key (or GROQ_API_KEY env)")
    sub = parser.add_subparsers(dest="command", required=True)

    # create-requirements
    p_create = sub.add_parser("create-requirements", help="Stage A+B: Extract requirements from JD, save artifact")
    p_create.add_argument("jd_file", type=Path, help="Path to job description file")
    p_create.add_argument("--role-id", help="Role identifier (default: derived from JD hash)")
    p_create.set_defaults(func=cmd_create_requirements)

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Stage C+D: Evaluate resume against frozen requirements")
    p_eval.add_argument("resume", type=Path, help="Path to resume PDF or text file")
    p_eval.add_argument("--role-id", required=True, help="Role ID from create-requirements")
    p_eval.add_argument("--jd-hash", required=True, help="JD hash from create-requirements")
    p_eval.add_argument("--reports-dir", type=Path, default=Path("artifacts"), help="Directory for run_report.json")
    p_eval.add_argument("--json", action="store_true", help="Output JSON")
    p_eval.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
