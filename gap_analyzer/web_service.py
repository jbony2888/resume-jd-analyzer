"""Web app service layer - Groq API logic ported from React app."""

import json
import os
import re
from groq import Groq

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")  # Exported for audit logging

# --- MOCK DATA (matches React MOCK_JD_RESPONSE, MOCK_RESUME_RESPONSE) ---
MOCK_JD_RESPONSE = {
    "role_title": "Senior Python Engineer",
    "requirements": [
        {"category": "Technical", "name": "Python", "importance": "Must-have", "description": "5+ years production experience"},
        {"category": "Technical", "name": "Django/Flask", "importance": "Must-have", "description": "Experience building REST APIs"},
        {"category": "Infrastructure", "name": "AWS", "importance": "Must-have", "description": "EC2, Lambda, S3"},
        {"category": "Technical", "name": "Kubernetes", "importance": "Nice-to-have", "description": "Container orchestration"},
        {"category": "Behavioral", "name": "Mentorship", "importance": "Must-have", "description": "Mentoring junior devs"},
    ],
}

MOCK_RESUME_RESPONSE = {
    "candidate_name": "Jane Doe",
    "signals": [
        {"category": "Technical", "name": "Python", "evidence": "Built high-scale data pipelines processing 1TB/day", "years_experience": 6},
        {"category": "Technical", "name": "Flask", "evidence": "Developed microservices for payment gateway", "years_experience": 4},
        {"category": "Infrastructure", "name": "AWS Lambda", "evidence": "Serverless architecture for image processing", "years_experience": 3},
        {"category": "Behavioral", "name": "Team Lead", "evidence": "Led a squad of 4 engineers", "years_experience": 2},
    ],
}


def _call_groq(api_key: str, system_prompt: str, user_text: str, json_mode: bool = True) -> dict:
    """Call Groq API - matches React callGroq behavior."""
    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": system_prompt + (" Return strictly valid JSON." if json_mode else "")},
        {"role": "user", "content": user_text},
    ]
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content.strip()
    return json.loads(content)


def analyze_jd(api_key: str, jd_text: str, use_mock: bool = False) -> dict:
    """Extract structured requirements from Job Description."""
    if use_mock:
        return MOCK_JD_RESPONSE

    prompt = """You are an expert HR decision system. Extract structured requirements from the Job Description.
Output JSON with this schema:
{
  "role_title": "string",
  "requirements": [
    { "category": "Technical|Domain|Behavioral", "name": "Skill Name", "importance": "Must-have|Nice-to-have", "description": "Context" }
  ]
}"""
    return _call_groq(api_key, prompt, jd_text)


def analyze_resume(api_key: str, resume_text: str, use_mock: bool = False) -> dict:
    """Extract proven skills and experience signals from résumé."""
    if use_mock:
        return MOCK_RESUME_RESPONSE

    prompt = """You are a technical screener. Extract proven skills and experience signals from the résumé.
Focus on evidence, not just keywords.
Output JSON with this schema:
{
  "candidate_name": "string",
  "signals": [
    { "category": "Technical|Domain|Behavioral", "name": "Skill Name", "evidence": "Evidence quote", "years_experience": number }
  ]
}"""
    return _call_groq(api_key, prompt, resume_text)


def tailor_resume(api_key: str, original_resume: str, jd_text: str, use_mock: bool = False) -> str:
    """Rewrite resume to highlight matches with JD."""
    if use_mock:
        return "Mock tailored resume content based on your instructions..."

    prompt = """You are an expert resume writer.
I will provide a candidate's original resume content and a target Job Description.
Your goal is to rewrite the resume to better align with the JD, highlighting the matching skills found in the analysis.

Rules:
1. Do NOT fabricate experience. Only use facts from the original resume.
2. Rephrase bullet points to use keywords from the JD where truthful.
3. Emphasize transferrable skills for any missing requirements.
4. Use clean markdown structure for professional PDF output:
   - # Name (centered at top)
   - ## Major sections (e.g. ## Contact Information, ## Summary, ## Core Skills, ## Experience)
   - ### Sub-sections if needed
   - Category labels in ALL CAPS (e.g. LANGUAGES, FRAMEWORKS & PLATFORMS) for skill groupings
   - #### Job Title — Company or Project
   - - Bullet points for achievements
   - Use "Impact" as a sub-heading before impact bullets where applicable
5. Output the result as a JSON object with a single field "tailored_text" containing the full markdown formatted resume.
"""
    input_text = f"Original Resume: {original_resume}\n\nTarget JD: {jd_text}"
    result = _call_groq(api_key, prompt, input_text)
    return result.get("tailored_text", "")


def refine_resume(
    api_key: str,
    original_resume: str,
    jd_text: str,
    refinement_instructions: str,
    use_mock: bool = False,
) -> str:
    """Refine resume with specific user instructions."""
    if use_mock:
        return "Mock refined resume based on: " + refinement_instructions

    prompt = f"""You are an expert resume writer.
I will provide a candidate's original resume content and a target Job Description.
The user has provided specific refinement instructions to improve the current draft.

Refinement Instructions: "{refinement_instructions}"

Your goal is to rewrite the resume to better align with the JD AND strictly satisfy the user's instructions.

Rules:
1. Do NOT fabricate experience. Only use facts from the original resume.
2. Rephrase bullet points to use keywords from the JD where truthful.
3. Use clean markdown: # Name, ### SECTION HEADER (uppercase), #### Job Title, - bullets.
4. Output the result as a JSON object with a single field "tailored_text" containing the full markdown formatted resume.
"""
    input_text = f"Original Resume: {original_resume}\n\nTarget JD: {jd_text}"
    result = _call_groq(api_key, prompt, input_text)
    return result.get("tailored_text", "")


def perform_gap_analysis(jd_result: dict, resume_result: dict) -> tuple[list[dict], int]:
    """
    Client-side gap analysis - matches React performGapAnalysis.
    Returns (gap_report, match_score).
    """
    jd_reqs = jd_result.get("requirements", [])
    resume_signals = resume_result.get("signals", [])

    matches = 0
    report = []

    for req in jd_reqs:
        req_name = req["name"].lower()
        match = None
        for sig in resume_signals:
            sig_name = sig["name"].lower()
            if sig_name in req_name or req_name in sig_name:
                match = sig
                break

        if match:
            matches += 1

        status = "MATCH" if match else ("MISSING" if req.get("importance") == "Must-have" else "GAP")
        evidence = match["evidence"] if match else "No evidence found in extracted signals."

        report.append({
            **req,
            "status": status,
            "evidence": evidence,
        })

    total = len(jd_reqs) if jd_reqs else 1
    match_score = round((matches / total) * 100)

    return report, match_score
