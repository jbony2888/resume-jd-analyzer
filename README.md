# resume-jd-analyzer

AI-powered Job Description & Résumé Gap Analyzer using the Groq API (Llama 3).

## Quick Start

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Key

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
GROQ_API_KEY=gsk_your_key_here
```

Get an API key at [console.groq.com](https://console.groq.com).

### 4. Run the Analyzer

**Basic usage** (résumé PDF + job description file):

```bash
python main.py resume.pdf job_description.txt -o tailored_resume.pdf
```

**With inline job description:**

```bash
python main.py resume.pdf placeholder.txt --jd-text "Senior Python Developer with 5+ years experience..."
```

**Analysis only** (no PDF output):

```bash
python main.py resume.pdf job_description.txt --no-pdf
```

**JSON output:**

```bash
python main.py resume.pdf job_description.txt --json
```

### 5. Run the Web App (React-style UI)

A Flask web app replicates the full React interface:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

**Master résumé:** Upload your base résumé once (PDF or TXT). It's saved to `resumes/master/` and used for all JD gap analyses. Paste different job descriptions and run analysis without re-uploading.

**Logs & audit trail:**
- **Console** – INFO-level logs stream to the terminal
- **`logs/app.log`** – Full app log (DEBUG+)
- **`logs/audit.log`** – JSONL audit trail (timestamp, action, status, model, char counts, match_score, errors)
- **`logs/model_performance.jsonl`** – Per-run model performance (time, model, match_score, criteria_used, gap_details, scoring_rationale)
- **`logs/model_performance.csv`** – Same data in CSV for spreadsheet review

You can:

- Paste job description and upload résumé (PDF or TXT)
- Run gap analysis with Groq (or use Mock Mode without API key)
- Generate tailored résumé, refine with instructions, download PDF
- View extracted JD/resume signals and detailed comparison table

## Features

- **PDF Parsing**: Extracts text from résumé PDFs using pypdf
- **AI Analysis**: Uses Groq (Llama 3) to analyze the gap between JD and résumé
- **PDF Generation**: Generates tailored résumés with recommendations using ReportLab

## Deterministic Resume-to-Job Matching Pipeline

The pipeline produces **deterministic, auditable, reproducible** scores by freezing requirements once per job and using code-only scoring.

### (a) Create requirements artifact for a JD

Extract and normalize requirements from a job description, then save a frozen artifact:

```bash
python cli_pipeline.py create-requirements sample_jd.txt
```

Optional `--role-id`:

```bash
python cli_pipeline.py create-requirements sample_jd.txt --role-id "senior_python"
```

This writes `artifacts/job_requirements.<role_id>.<jd_hash>.v1.json`. Note the `role_id` and `jd_hash` printed—you need them for evaluation.

### (b) Run evaluation against a resume using frozen requirements

Evaluate a resume against a previously created requirements artifact:

```bash
python cli_pipeline.py evaluate resume.pdf --role-id <role_id> --jd-hash <jd_hash>
```

Example (using values from create-requirements output):

```bash
python cli_pipeline.py evaluate resumes/master/Master-Copy-Resume.pdf --role-id role_abc123def456 --jd-hash a1b2c3...64chars
```

`--json` outputs the full score and metadata. `run_report.json` is written to `artifacts/` for audit.

### (c) Run tests

```bash
python -m pytest tests/ -v
```

Tests include:

- **Determinism**: same requirements + evidence map → identical scores across 10 runs
- **Requirements missing**: evaluation fails if the requirements artifact is absent (no silent regeneration)
- **Evidence required**: matches with `matched=true` must have at least one evidence quote
- **Idempotency**: run same (resume, JD) N times → identical requirement IDs, matches, and scores (requires `GROQ_API_KEY`)

**Idempotency check script** (variance report):

```bash
python scripts/run_idempotency_check.py --runs 10
```

## Project Structure

```
gap_analyzer/
  __init__.py
  pdf_parser.py     # Extract text from PDF
  analyzer.py       # Groq AI gap analysis
  pdf_generator.py  # Generate tailored PDFs
  web_service.py    # JD/Resume/Tailor/Refine API logic (from React)
  tailored_pdf.py   # Markdown-aware PDF for tailored resumes
src/
  pipeline/         # Extract, normalize, artifacts, match (Stages A–C)
  scoring/          # Deterministic scoring engine (Stage D)
  validation.py     # Schema validation
  run_report.py     # Audit report generation
schemas/            # JSON schemas for requirements and evidence map
artifacts/          # Frozen requirements and evidence artifacts
prompts/            # LLM prompts (extract_requirements, match_evidence)
tests/              # Determinism, requirements_missing, evidence_required
app.py              # Flask web app (React-style UI)
main.py             # CLI for legacy gap analysis
cli_pipeline.py     # CLI for deterministic pipeline
templates/index.html
requirements.txt
.env.example
```
