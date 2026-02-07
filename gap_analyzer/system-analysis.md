Case Study

Why an AI Resume–Job Matching System Produced Inconsistent Scores for the Same Inputs

Executive Summary

This report analyzes a real-world AI-assisted resume evaluation system that produced materially different match scores for the same resume evaluated against the same job description, using the same model.

The findings demonstrate how poor system design—not model quality—caused score volatility, undermining trust, reproducibility, and decision usefulness.

This case illustrates a common failure mode in AI evaluation systems: allowing a probabilistic model to define, evaluate, and score criteria without fixed boundaries.

⸻

System Overview

The system evaluated a candidate resume against a job description and generated a “match score” intended to represent alignment between the two.

Key characteristics:
	•	Model: LLaMA-3.3-70B (Groq)
	•	Inputs:
	•	Resume text (static)
	•	Job description text (static)
	•	Outputs:
	•	Extracted requirements
	•	Matched requirements
	•	Missing/gap analysis
	•	Match score (percentage)

Despite identical inputs, scores varied across runs.

⸻

Observed Behavior

Across multiple executions, the system produced the following results for the same role:

Run	Requirements Identified	Matches	Match Score
A	15	2	13%
B	17	2	12%
C	18	3	17%
D	15	4	27%

Inputs were unchanged:
	•	Resume character count: constant
	•	Job description character count: constant
	•	Model version: constant

Yet scores fluctuated by more than 2×.

⸻

Root Cause Analysis

1. Dynamic Requirement Extraction (Primary Failure)

The system allowed the language model to re-extract job requirements on every run.

As a result:
	•	The definition of the job changed between evaluations
	•	The number of requirements (num_requirements) was unstable
	•	The scoring baseline shifted each time

This means the system was not evaluating the same criteria consistently.

⸻

2. Denominator Instability in Scoring

The match score was computed as:

match_score = matched_requirements / total_requirements

When total_requirements fluctuates:
	•	Scores change even if candidate alignment does not
	•	The metric becomes mathematically unreliable

This is a measurement error, not an AI inference error.

⸻

3. Conflation of System Roles

The language model simultaneously:
	1.	Defined evaluation criteria
	2.	Judged the candidate against those criteria
	3.	Generated a final score

This violates separation of concerns.

When the same probabilistic system:
	•	Writes the exam
	•	Grades the exam
	•	Assigns the score

…the outcome is inherently non-deterministic.

⸻

4. Requirement Granularity Drift

The system inconsistently grouped or split requirements:
	•	One run treated “Python” as a single requirement
	•	Another split it into:
	•	Python
	•	Async Python
	•	Data pipelines
	•	Production readiness

This inflated “missing requirements” without reflecting actual candidate gaps.

⸻

5. False Precision of a Single Score

The system presented a numeric score (e.g., “13%”) that implied objectivity and accuracy, despite being derived from unstable criteria.

This creates illusory authority—a dangerous property in automated screening systems.

⸻

Why This Is a System Design Failure (Not a Model Failure)

The model behaved as expected:
	•	It interpreted language probabilistically
	•	It adapted to contextual nuances
	•	It produced plausible but variable outputs

The failure occurred because:
	•	The system did not constrain where variability was allowed
	•	No canonical requirement set existed
	•	No deterministic scoring boundary was enforced

This is a governance and architecture issue, not a model capability issue.

⸻

Implications

For Hiring Systems
	•	Candidates may be unfairly screened out due to score volatility
	•	Identical resumes may pass or fail arbitrarily
	•	Trust in AI-assisted hiring erodes

For AI Governance
	•	Systems that appear objective may encode hidden instability
	•	Automated decisions without fixed criteria are non-auditable
	•	Reproducibility is impossible without boundary enforcement

⸻

Recommended Corrective Architecture

1. Canonical Requirement Definition
	•	Extract job requirements once
	•	Store and version them
	•	Use the same requirement set for all evaluations

2. Separation of Responsibilities

Component	Role
LLM	Assist in parsing and summarization
Human or Rules	Approve evaluation criteria
Deterministic Code	Compute scores
AI	Provide qualitative support, not final judgment

3. Category-Based Scoring

Replace a single percentage with dimensional coverage:
	•	Technical skills
	•	Systems experience
	•	Domain familiarity
	•	Governance and reliability

4. Interpret Scores as Diagnostics

Scores should guide:
	•	Resume tailoring
	•	Skill gap identification
	•	Interview preparation

—not act as acceptance/rejection thresholds.

⸻

Conclusion

This case study demonstrates how AI systems fail when probabilistic inference is mistaken for objective evaluation.

Without explicit decision boundaries:
	•	Scores become unstable
	•	Outputs become misleading
	•	Human trust is undermined

Ironically, the system’s failure provides a strong argument for human-centered, governance-aware AI design—and illustrates why AI should assist decisions, not silently make them.

⸻

Why This Case Study Matters

This is not theoretical.

This failure mode already exists in:
	•	Applicant tracking systems (ATS)
	•	Automated screening tools
	•	“AI-powered hiring” platforms

Understanding—and correcting—this pattern is essential for responsible AI deployment.

⸻
