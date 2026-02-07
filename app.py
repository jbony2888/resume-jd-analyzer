#!/usr/bin/env python3
"""Flask web app for JD-Résumé Gap Analyzer - port of React app."""

import json
import os
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

from gap_analyzer.pdf_parser import extract_text_from_pdf
from gap_analyzer.web_service import (
    MODEL,
    analyze_jd,
    analyze_resume,
    tailor_resume,
    refine_resume,
    perform_gap_analysis,
)
from gap_analyzer.frozen_pipeline import run_frozen_analysis
from gap_analyzer.tailored_pdf import generate_tailored_pdf
from gap_analyzer.audit import audit_log, log_model_performance, setup_app_logging

load_dotenv()

log = setup_app_logging()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

SAMPLE_JD = """We are looking for a Senior Python Engineer to lead our backend team.
Requirements:
- 5+ years of experience with Python, specifically building REST APIs with Django or Flask.
- Deep understanding of AWS services (EC2, Lambda, S3).
- Experience with Kubernetes is a plus.
- Must have strong communication skills and experience mentoring junior developers."""

SAMPLE_RESUME = """Jane Doe
Software Engineer

Summary:
Senior developer with 6 years of experience in Python.
- Built high-scale data pipelines using Python and Flask processing 1TB/day.
- Designed serverless architectures using AWS Lambda and S3.
- Led a squad of 4 engineers, conducting code reviews and sprint planning.
- Passionate about clean code and testing."""


@app.route("/")
def index():
    return render_template("index.html", sample_jd=SAMPLE_JD)


@app.route("/api/requirements/build", methods=["POST"])
def api_requirements_build():
    """Create frozen requirements artifact from JD. Must be run before /api/analyze for that JD."""
    data = request.get_json() or {}
    jd_text = data.get("jd_text", "").strip()
    api_key = (data.get("api_key") or "").strip() or os.environ.get("GROQ_API_KEY", "")

    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400
    if not api_key:
        return jsonify({"error": "GROQ_API_KEY is not set. Add it to .env in the project root."}), 400

    try:
        from src.utils import hash_text
        from src.pipeline.extract import extract_requirements_from_jd, MODEL_ID as EXTRACT_MODEL
        from src.pipeline.artifacts import save_requirements_artifact, load_requirements_artifact_by_jd_hash

        jd_hash = hash_text(jd_text)
        try:
            requirements_doc, path = load_requirements_artifact_by_jd_hash(jd_hash)
            extract_model = EXTRACT_MODEL  # cached artifact; current extract model for audit
            log.info("Requirements artifact already exists for jd_hash=%s, skipping extraction", jd_hash[:16])
        except FileNotFoundError:
            requirements_doc = extract_requirements_from_jd(api_key, jd_text)
            extract_model = requirements_doc.get("_audit", {}).get("model_id", EXTRACT_MODEL)
            # Strip _audit before saving (audit metadata not part of canonical artifact)
            to_save = {k: v for k, v in requirements_doc.items() if k != "_audit"}
            path = save_requirements_artifact(
                requirements_doc["role_id"],
                requirements_doc["jd_hash"],
                to_save,
            )
        audit_log(
            action="requirements_build",
            status="success",
            use_mock=False,
            model=extract_model,
            jd_char_count=len(jd_text),
            extra={
                "jd_hash": requirements_doc["jd_hash"],
                "role_id": requirements_doc["role_id"],
                "num_requirements": len(requirements_doc["requirements"]),
                "artifact_path": str(path),
            },
        )
        log.info("Requirements artifact built: jd_hash=%s num_reqs=%d", requirements_doc["jd_hash"][:16], len(requirements_doc["requirements"]))
        return jsonify({
            "jd_hash": requirements_doc["jd_hash"],
            "role_id": requirements_doc["role_id"],
            "num_requirements": len(requirements_doc["requirements"]),
            "artifact_path": str(path),
        })
    except Exception as e:
        audit_log(
            action="requirements_build",
            status="error",
            use_mock=False,
            jd_char_count=len(jd_text),
            error=str(e),
        )
        log.exception("Requirements build failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Run JD + Resume analysis and gap report."""
    data = request.get_json() or {}
    jd_text = data.get("jd_text", "").strip()
    resume_text = data.get("resume_text", "").strip()
    api_key = (data.get("api_key") or "").strip() or os.getenv("GROQ_API_KEY", "")
    use_mock = data.get("use_mock", False)

    if not jd_text or not resume_text:
        return jsonify({"error": "Job description and résumé text are required"}), 400
    if not api_key and not use_mock:
        return jsonify({"error": "GROQ_API_KEY is not set. Add it to .env in the project root."}), 400

    log.info("Analyze started (api_key_set=%s, jd_chars=%d, resume_chars=%d)", bool(api_key), len(jd_text), len(resume_text))

    try:
        if use_mock:
            jd_result = analyze_jd(api_key, jd_text, use_mock)
            resume_result = analyze_resume(api_key, resume_text, use_mock)
            gap_report, match_score = perform_gap_analysis(jd_result, resume_result)
            result = {
                "jd_analysis": jd_result,
                "resume_analysis": resume_result,
                "gap_report": gap_report,
                "match_score": match_score,
                "requirements_source": "generated",
                "jd_hash": None,
                "resume_hash": None,
                "requirements_version": None,
                "requirements_artifact_path": None,
                "num_requirements": len(jd_result.get("requirements", [])),
                "must_have_coverage": None,
                "nice_to_have_coverage": None,
            }
        else:
            result = run_frozen_analysis(api_key, jd_text, resume_text)
            if result.get("requirements_source") != "artifact":
                raise RuntimeError("requirements_source must be 'artifact'; internal error")

        # Log actual model used (match stage); fallback to env for backward compat
        model_name = result.get("model_id") or MODEL if not use_mock else "mock"
        audit_log(
            action="analyze",
            status="success",
            use_mock=use_mock,
            model=model_name,
            jd_char_count=len(jd_text),
            resume_char_count=len(resume_text),
            match_score=result["match_score"],
            extra={
                "role_title": result["jd_analysis"].get("role_title"),
                "candidate_name": result["resume_analysis"].get("candidate_name"),
                "jd_hash": result.get("jd_hash"),
                "resume_hash": result.get("resume_hash"),
                "requirements_version": result.get("requirements_version"),
                "requirements_source": result.get("requirements_source"),
                "requirements_artifact_path": result.get("requirements_artifact_path"),
                "requirements_hash": result.get("requirements_hash"),
                "num_requirements": result.get("num_requirements"),
                "matched_count_raw": result.get("matched_count_raw"),
                "matched_count_validated": result.get("matched_count_validated"),
                "invalid_quote_count": result.get("invalid_quote_count"),
                "evidence_prompt_includes_description": result.get("evidence_prompt_includes_description"),
                "prompt_version": result.get("prompt_version"),
                "prompt_hash": result.get("prompt_hash"),
                "model_params": result.get("model_params"),
            },
        )
        log_model_performance(
            model=model_name,
            use_mock=use_mock,
            match_score=result["match_score"],
            role_title=result["jd_analysis"].get("role_title", ""),
            candidate_name=result["resume_analysis"].get("candidate_name", ""),
            criteria_used=result["jd_analysis"].get("requirements", []),
            gap_report=result["gap_report"],
            jd_char_count=len(jd_text),
            resume_char_count=len(resume_text),
            jd_hash=result.get("jd_hash"),
            resume_hash=result.get("resume_hash"),
            requirements_version=result.get("requirements_version"),
            requirements_source=result.get("requirements_source"),
            requirements_artifact_path=result.get("requirements_artifact_path"),
            prompt_version=result.get("prompt_version"),
            prompt_hash=result.get("prompt_hash"),
            model_params=result.get("model_params"),
            normalized_requirement_count=result.get("num_requirements"),
            matched_count=result.get("matched_count"),
            requirements_hash=result.get("requirements_hash"),
            matched_count_raw=result.get("matched_count_raw"),
            matched_count_validated=result.get("matched_count_validated"),
            invalid_quote_count=result.get("invalid_quote_count"),
            evidence_prompt_includes_description=result.get("evidence_prompt_includes_description"),
        )
        log.info("Analyze complete: match_score=%d%% requirements_source=%s", result["match_score"], result.get("requirements_source"))

        return jsonify({
            "jd_analysis": result["jd_analysis"],
            "resume_analysis": result["resume_analysis"],
            "gap_report": result["gap_report"],
            "match_score": result["match_score"],
            "jd_hash": result.get("jd_hash"),
            "resume_hash": result.get("resume_hash"),
            "requirements_version": result.get("requirements_version"),
            "requirements_source": result.get("requirements_source"),
            "requirements_artifact_path": result.get("requirements_artifact_path"),
            "num_requirements": result.get("num_requirements"),
            "must_have_coverage": result.get("must_have_coverage"),
            "nice_to_have_coverage": result.get("nice_to_have_coverage"),
        })
    except FileNotFoundError as e:
        audit_log(
            action="analyze",
            status="error",
            use_mock=use_mock,
            jd_char_count=len(jd_text),
            resume_char_count=len(resume_text),
            error=str(e),
            extra={"error_type": "Requirements artifact missing"},
        )
        log.warning("Analyze failed: requirements artifact missing")
        return jsonify({
            "error": "Requirements artifact missing. Run POST /api/requirements/build first with the same JD.",
            "code": "REQUIREMENTS_MISSING",
        }), 409
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Invalid API Key" in err_msg or "invalid_api_key" in err_msg:
            err_msg = "Invalid or expired API key. Check GROQ_API_KEY in .env and regenerate at console.groq.com"
        audit_log(
            action="analyze",
            status="error",
            use_mock=use_mock,
            jd_char_count=len(jd_text),
            resume_char_count=len(resume_text),
            error=err_msg,
        )
        log.exception("Analyze failed")
        return jsonify({"error": err_msg}), 500


@app.route("/api/tailor", methods=["POST"])
def api_tailor():
    """Generate tailored resume."""
    data = request.get_json() or {}
    original_resume = data.get("resume_text", "").strip()
    jd_text = data.get("jd_text", "").strip()
    api_key = (data.get("api_key") or "").strip() or os.getenv("GROQ_API_KEY", "")
    use_mock = data.get("use_mock", False)

    if not original_resume or not jd_text:
        return jsonify({"error": "Resume and job description are required"}), 400
    if not api_key and not use_mock:
        return jsonify({"error": "GROQ_API_KEY is not set. Add it to .env in the project root."}), 400

    log.info("Tailor started (api_key_set=%s)", bool(api_key))
    try:
        tailored = tailor_resume(api_key, original_resume, jd_text, use_mock)
        audit_log(
            action="tailor",
            status="success",
            use_mock=use_mock,
            model=MODEL if not use_mock else None,
            jd_char_count=len(jd_text),
            resume_char_count=len(original_resume),
            extra={"output_char_count": len(tailored)},
        )
        log.info("Tailor complete: output_chars=%d", len(tailored))
        return jsonify({"tailored_text": tailored})
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Invalid API Key" in err_msg or "invalid_api_key" in err_msg:
            err_msg = "Invalid or expired API key. Check GROQ_API_KEY in .env and regenerate at console.groq.com"
        audit_log(action="tailor", status="error", use_mock=use_mock, error=err_msg)
        log.exception("Tailor failed")
        return jsonify({"error": err_msg}), 500


@app.route("/api/refine", methods=["POST"])
def api_refine():
    """Refine tailored resume with instructions."""
    data = request.get_json() or {}
    original_resume = data.get("resume_text", "").strip()
    jd_text = data.get("jd_text", "").strip()
    instructions = data.get("refine_instructions", "").strip()
    api_key = (data.get("api_key") or "").strip() or os.getenv("GROQ_API_KEY", "")
    use_mock = data.get("use_mock", False)

    if not instructions:
        return jsonify({"error": "Refinement instructions are required"}), 400
    if not original_resume or not jd_text:
        return jsonify({"error": "Resume and job description are required"}), 400
    if not api_key and not use_mock:
        return jsonify({"error": "GROQ_API_KEY is not set. Add it to .env in the project root."}), 400

    log.info("Refine started (api_key_set=%s, instructions_len=%d)", bool(api_key), len(instructions))
    try:
        tailored = refine_resume(api_key, original_resume, jd_text, instructions, use_mock)
        audit_log(
            action="refine",
            status="success",
            use_mock=use_mock,
            model=MODEL if not use_mock else None,
            jd_char_count=len(jd_text),
            resume_char_count=len(original_resume),
            extra={"instructions_len": len(instructions), "output_char_count": len(tailored)},
        )
        log.info("Refine complete")
        return jsonify({"tailored_text": tailored})
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Invalid API Key" in err_msg or "invalid_api_key" in err_msg:
            err_msg = "Invalid or expired API key. Check GROQ_API_KEY in .env and regenerate at console.groq.com"
        audit_log(action="refine", status="error", use_mock=use_mock, error=err_msg)
        log.exception("Refine failed")
        return jsonify({"error": err_msg}), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Extract text from uploaded PDF or TXT file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    log.info("Upload started: filename=%s", file.filename)
    try:
        if file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf"):
            tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"gap_analyzer_{os.getpid()}_{file.filename}"
            file.save(tmp)
            try:
                text = extract_text_from_pdf(tmp)
            finally:
                tmp.unlink(missing_ok=True)
        else:
            text = file.read().decode("utf-8", errors="replace")

        audit_log(
            action="upload",
            status="success",
            filename=file.filename,
            extra={"resume_char_count": len(text)},
        )
        log.info("Upload complete: filename=%s, chars=%d", file.filename, len(text))
        return jsonify({"text": text, "filename": file.filename})
    except Exception as e:
        audit_log(action="upload", status="error", filename=file.filename, error=str(e))
        log.exception("Upload failed")
        return jsonify({"error": str(e)}), 500


RESUMES_DIR = Path(__file__).resolve().parent / "resumes"
MASTER_DIR = RESUMES_DIR / "master"


def _get_master_file() -> Path | None:
    """Return path to the master resume file if it exists."""
    if not MASTER_DIR.exists():
        return None
    for f in MASTER_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in (".pdf", ".txt"):
            return f
    return None


def _read_master_resume() -> dict:
    """Read master resume from folder. Returns {text, filename} or {text: None}."""
    path = _get_master_file()
    if not path:
        return {"text": None, "filename": None}
    try:
        if path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": text, "filename": path.name}
    except Exception as e:
        log.warning("Failed to read master resume: %s", e)
        return {"text": None, "filename": None}


@app.route("/api/master-resume", methods=["GET"])
def api_get_master_resume():
    """Return the stored master resume (used as base for all gap analyses)."""
    data = _read_master_resume()
    return jsonify(data)


@app.route("/api/master-resume", methods=["POST"])
def api_set_master_resume():
    """Save uploaded PDF/TXT to master folder. Overwrites any existing master file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith((".pdf", ".txt")):
        return jsonify({"error": "Only PDF and TXT files are allowed"}), 400
    log.info("Saving master resume: filename=%s", file.filename)
    try:
        MASTER_DIR.mkdir(parents=True, exist_ok=True)
        # Remove any existing master file (keep only one)
        for f in MASTER_DIR.iterdir():
            if f.is_file():
                f.unlink()
        # Save the new file
        save_path = MASTER_DIR / file.filename
        file.save(str(save_path))
        data = _read_master_resume()
        log.info("Master resume saved to %s", save_path)
        return jsonify(data)
    except Exception as e:
        log.exception("Failed to save master resume")
        return jsonify({"error": str(e)}), 500


def _sanitize_folder_name(name: str) -> str:
    """Convert company name to safe folder name."""
    safe = "".join(c if c not in r'\/:*?"<>|' else "_" for c in name)
    return safe.strip() or "General"


@app.route("/api/download-pdf", methods=["POST"])
def api_download_pdf():
    """Generate, save to company folder, and return tailored resume PDF."""
    data = request.get_json() or {}
    tailored_text = data.get("tailored_text", "").strip()
    candidate_name = data.get("candidate_name", "Candidate")
    company_name = _sanitize_folder_name((data.get("company_name") or "").strip() or "General")

    if not tailored_text:
        return jsonify({"error": "Tailored text is required"}), 400

    log.info("Download PDF: candidate=%s, company=%s", candidate_name, company_name)
    try:
        pdf_bytes = generate_tailored_pdf(tailored_text, candidate_name)
        filename = f"{candidate_name.replace(' ', '_')}_Tailored_Resume.pdf"
        save_dir = RESUMES_DIR / company_name
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        save_path.write_bytes(pdf_bytes)
        log.info("Saved to %s", save_path)
        audit_log(
            action="download_pdf",
            status="success",
            filename=filename,
            extra={"candidate_name": candidate_name, "company_name": company_name, "save_path": str(save_path), "pdf_bytes": len(pdf_bytes)},
        )
        from io import BytesIO
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        audit_log(action="download_pdf", status="error", error=str(e))
        log.exception("Download PDF failed")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    api_key_set = bool(os.getenv("GROQ_API_KEY", "").strip())
    log.info(
        "GapAnalyzer starting on http://127.0.0.1:5000 | GROQ_API_KEY set: %s | Logs: logs/app.log | Audit: logs/audit.log",
        api_key_set,
    )
    if not api_key_set:
        log.warning("GROQ_API_KEY not found in .env - analysis will fail until it is set")
    app.run(debug=True, port=5000)
