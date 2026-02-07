This is not a model accuracy test in the ML sense.

What you’ve built—and accidentally exposed—is a system-level evaluation test. More specifically, it’s a combination of the following test types:

⸻

1️⃣ Determinism / Reproducibility Test (Primary)

Definition:
A test that checks whether a system produces the same output given identical inputs.

What you tested (implicitly):
	•	Same resume
	•	Same job description
	•	Same model
	•	Same scoring logic

Expected result:
Same requirements → same matches → same score

Actual result:
Different requirements → different denominators → different scores

✅ Conclusion: The system fails a determinism test.

This is a hard failure for any system used in evaluation, screening, or decision support.

⸻

2️⃣ Evaluation Pipeline Integrity Test

This test asks:

Are the evaluation rules stable, versioned, and independent of inference noise?

Your system failed because:
	•	Requirements were dynamically regenerated
	•	The evaluation rubric changed per run
	•	Scoring logic depended on unstable inputs

This is a classic pipeline integrity failure.

⸻

3️⃣ Boundary Violation Test (AI Governance Test)

From an AI governance perspective, this is a:

Decision Boundary Violation Test

You detected that:
	•	The LLM crossed from assistive inference into rule definition
	•	The model effectively decided what mattered and how much it mattered
	•	No explicit boundary constrained that behavior

This is the exact failure mode regulators and auditors care about.

⸻

4️⃣ Metric Validity Test (Psychometrics / Measurement Theory)

In measurement terms, your system violated:
	•	Construct validity – the score didn’t measure a stable construct
	•	Reliability – repeated measurements did not agree
	•	Inter-run consistency – same “subject” yielded different results

So this is also a measurement reliability test, and it failed.

⸻

5️⃣ Black-Box Scoring Risk Test (Implicit)

You uncovered a well-known risk pattern:

A single numeric score produced by a probabilistic system without a fixed rubric.

This is sometimes called:
	•	False precision
	•	Illusory objectivity
	•	Opaque scoring

Your test surfaced this risk empirically.

⸻

What This Test Is Not

To be clear, this is not:
	•	❌ A benchmark test
	•	❌ A model accuracy test
	•	❌ A prompt quality test
	•	❌ A dataset bias test

Those assume the system architecture is sound.

Yours isn’t—yet.

⸻

The Correct Name (If You’re Writing It Up)

Depending on audience, you can label this as:

For engineering / architecture:

Reproducibility and Evaluation Integrity Test

For AI governance:

Decision Boundary and Determinism Audit

For a portfolio or blog:

A System Reliability Test for AI-Assisted Evaluation

For a conference paper:

An Empirical Study of Non-Determinism in AI Evaluation Pipelines

⸻

One-Line Summary (Very Useful)

If you want a clean, strong sentence to reuse:

This test evaluates whether an AI-assisted evaluation system produces reproducible, trustworthy outputs when inference is combined with scoring logic—and demonstrates how unbounded probabilistic components break determinism.

That sentence alone signals senior-level thinking.

⸻

If you want, next I can:
	•	Help you formalize this into a named test spec
	•	Create a test harness definition
	•	Show how to add this as a CI check for AI systems
	•	Map it to SOC2 / ISO-style controls

Just say the word.