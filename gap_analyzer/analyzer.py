"""AI-powered gap analysis between Job Descriptions and Résumés using Groq."""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "llama-3.1-70b-versatile"


class GapAnalyzer:
    """Analyzes the gap between a Job Description and a Résumé using Groq (Llama 3)."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Set it in .env or pass api_key to GapAnalyzer."
            )
        self.client = Groq(api_key=self.api_key)
        self.model = model

    def analyze(
        self,
        job_description: str,
        resume_text: str,
        structured: bool = True,
    ) -> str | dict:
        """
        Analyze the gap between a job description and a résumé.

        Args:
            job_description: The full job description text.
            resume_text: The résumé text (e.g., extracted from PDF).
            structured: If True, request structured JSON output for programmatic use.

        Returns:
            Analysis text, or a dict if structured=True and parsing succeeds.
        """
        prompt = self._build_prompt(job_description, resume_text, structured)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()

        if structured:
            try:
                return self._parse_structured_response(content)
            except json.JSONDecodeError:
                return {"raw_analysis": content}

        return content

    def _build_prompt(self, jd: str, resume: str, structured: bool) -> str:
        base = """You are an expert career coach and recruiter. Analyze the gap between the following Job Description and Résumé.

Job Description:
---
{jd}
---

Résumé:
---
{resume}
---

Provide a detailed gap analysis that includes:
1. **Strengths**: Where the candidate aligns well with the role.
2. **Gaps**: Missing skills, experience, or qualifications.
3. **Recommendations**: Specific, actionable steps to bridge the gap (skills to learn, experience to highlight, phrasing to add).
4. **Keywords to add**: Important JD keywords the résumé should include.
5. **Overall fit score** (1-10) with brief justification.
"""

        if structured:
            base += """
Respond with valid JSON only, no markdown code blocks. Use this structure:
{
  "strengths": ["...", "..."],
  "gaps": ["...", "..."],
  "recommendations": ["...", "..."],
  "keywords_to_add": ["...", "..."],
  "fit_score": 7,
  "fit_justification": "..."
}
"""

        return base.format(jd=jd, resume=resume)

    def _parse_structured_response(self, content: str) -> dict:
        # Remove markdown code blocks if present
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
