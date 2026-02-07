#!/usr/bin/env python3
"""CLI for the JD-Résumé Gap Analyzer."""

import argparse
import json
import sys
from pathlib import Path

from gap_analyzer import extract_text_from_pdf, GapAnalyzer, ResumePDFGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Analyze the gap between a Job Description and a Résumé using Groq AI."
    )
    parser.add_argument(
        "resume_pdf",
        type=Path,
        help="Path to the résumé PDF file",
    )
    parser.add_argument(
        "job_description",
        type=Path,
        nargs="?",
        default=None,
        help="Path to the job description text file (or use --jd-text for inline)",
    )
    parser.add_argument(
        "--jd-text",
        type=str,
        help="Job description as inline text (overrides job_description file if set)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("tailored_resume.pdf"),
        help="Output path for the tailored résumé PDF (default: tailored_resume.pdf)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Only run analysis, do not generate PDF",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output analysis as JSON",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Groq API key (or set GROQ_API_KEY in .env)",
    )

    args = parser.parse_args()

    # Load job description
    if args.jd_text:
        jd_text = args.jd_text
    elif args.job_description:
        jd_path = Path(args.job_description)
        if not jd_path.exists():
            print(f"Error: Job description file not found: {jd_path}", file=sys.stderr)
            sys.exit(1)
        jd_text = jd_path.read_text(encoding="utf-8")
    else:
        print("Error: Provide job description via file or --jd-text", file=sys.stderr)
        sys.exit(1)

    # Extract résumé text
    try:
        resume_text = extract_text_from_pdf(args.resume_pdf)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not resume_text.strip():
        print("Warning: No text could be extracted from the résumé PDF.", file=sys.stderr)
        print("The PDF may be scanned. Consider using OCR.", file=sys.stderr)

    # Run analysis
    try:
        analyzer = GapAnalyzer(api_key=args.api_key)
        result = analyzer.analyze(
            job_description=jd_text,
            resume_text=resume_text,
            structured=args.json or not args.no_pdf,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.json:
        print(json.dumps(result if isinstance(result, dict) else {"raw_analysis": result}, indent=2))
    else:
        if isinstance(result, dict):
            print("=== Gap Analysis ===\n")
            for key in ["strengths", "gaps", "recommendations", "keywords_to_add", "fit_score", "fit_justification"]:
                val = result.get(key)
                if val is not None:
                    if isinstance(val, list):
                        print(f"{key.replace('_', ' ').title()}:")
                        for item in val:
                            print(f"  • {item}")
                        print()
                    else:
                        print(f"{key.replace('_', ' ').title()}: {val}\n")
        else:
            print(result)

    # Generate PDF if requested
    if not args.no_pdf:
        try:
            gen = ResumePDFGenerator(args.output)
            gen.generate_from_analysis(resume_text, result)
            print(f"\nTailored résumé saved to: {args.output}")
        except Exception as e:
            print(f"Error generating PDF: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
