# JD–Résumé Gap Analyzer — Historical Performance Report

**Report generated:** 2026-02-07  
**Data sources:** `audit.log`, `model_performance.csv`  
**Period:** 2026-02-07 00:13 UTC → 2026-02-07 18:47 UTC

---

## Executive Summary

The system went through four major phases:

1. **Pre-artifact era** – End-to-end LLM extraction + match; high score variance (12–27% on same JD).
2. **Frozen artifact adoption** – Requirements fixed per JD; match scores stabilized around 31–38% with 70B.
3. **8B switch & JD echo** – Model switch led to inflated 81% scores due to JD text leakage.
4. **Post-fix** – Guardrails and quote validation restored credible scores (20% on clean JD) with deterministic behavior.

---

## 1. Timeline Overview

| Period | Model | Requirements source | Match score range | Notes |
|--------|-------|---------------------|-------------------|-------|
| 00:13–01:19 | 70B | Generated (per run) | 12–27% | High variance; criteria drift |
| 02:16 | 70B | Extracted → artifact | — | 26-req artifact created (jd_hash 784a9663...) |
| 17:54–18:26 | 70B | Artifact | 31–38% | Stable; some run-to-run variance |
| 18:23 | 70B | Artifact | — | Schema error: `notes=None` |
| 18:29–18:47 | 8B | Artifact | 81% | Inflated; JD echo in evidence |
| Post-fix | 8B/70B | Artifact | 20% | Clean JD; validated; deterministic |

---

## 2. Score Variance Analysis

### Pre-artifact (generated requirements each run)

Same JD (10157 chars), same resume (7655 chars), same role (AI Staff Software Engineer):

| Timestamp | Model | num_reqs | match_score | num_matches |
|-----------|-------|----------|-------------|-------------|
| 00:13 | 70B | 15 | 13% | 2 |
| 00:18 | 70B | 17 | 12% | 2 |
| 00:38 | 70B | 15 | 13% | 2 |
| 00:45 | 70B | 18 | 17% | 3 |
| 00:49 | 70B | 15 | 27% | 4 |
| 00:51 | 70B | 15 | 27% | 4 |
| 01:18 | 70B | 17 | 12% | 2 |
| 01:19 | 70B | 15 | 13% | 2 |

**Root cause:** Extraction produced different requirement sets (15–18 requirements) and different splits (e.g., “AI and Machine Learning” vs “LLMs or Applied Machine Learning”). Denominator and criteria changed every run.

### Frozen artifact (26 requirements, jd_hash 784a9663...)

| Timestamp | Model | num_reqs | match_score | num_matches |
|-----------|-------|----------|-------------|-------------|
| 17:55 | 70B | 26 | 38% | 10 |
| 17:55 | 70B | 26 | 38% | 10 |
| 17:55 | 70B | 26 | 38% | 10 |
| 17:59 | 70B | 26 | 38% | 10 |
| 18:00 | 70B | 26 | 38% | 10 |
| 18:01 | 70B | 26 | 38% | 10 |
| 18:23 | 70B | 26 | 38% | 10 |
| 18:25 | 70B | 26 | 38% | 10 |
| 18:25 | 70B | 26 | 31% | 8 |
| 18:25 | 70B | 26 | 35% | 9 |
| 18:26 | 70B | 26 | 31% | 8 |
| 18:29 | 8B | 26 | **81%** | 21 |
| 18:30 | 8B | 26 | **81%** | 21 |
| 18:35 | 8B | 26 | **81%** | 21 |
| 18:36 | 8B | 26 | **81%** | 21 |
| 18:47 | 8B | 26 | **81%** | 21 |

**Findings:**
- 70B on artifact: mostly 38%, occasional 31–35% (match-stage variance).
- 8B on artifact: 81% (21/26 matched) — driven by JD echo in evidence.

---

## 3. Error Analysis

| Error type | Count | Example |
|------------|-------|---------|
| 401 Invalid API Key | 6 | API key expired/invalid |
| 429 Rate limit (70B) | 4 | TPD limit 100K exceeded |
| Requirements artifact missing | 1 | 409 before artifact created |
| Schema validation (notes=None) | 2 | LLM returned `notes: null` |
| download_pdf (float multiply) | 2 | Early bug, fixed |

---

## 4. Infrastructure Events

| Event | Timestamp | Details |
|-------|-----------|---------|
| First artifact creation | 02:16 | 26-req artifact for jd_hash 784a9663... |
| Rate limit hit | 01:19, 01:23, 18:26, 18:28 | 70B TPD exhausted |
| Switch to 8B | 18:29 | GROQ_MODEL=llama-3.1-8b-instant |
| notes sanitization | 18:25 | _sanitize_notes() added |
| JD leak fix | Post 18:47 | `description` removed from match payload |
| Quote validation | Post 18:47 | Hard validator, invalid_quote_count |

---

## 5. Post-Fix Validation (Repeatability Harness)

**Clean Headway JD (jd_hash 4304e276...), 10 requirements:**

| Model | Runs | match_score | invalid_quote_count | raw_vs_validated_delta |
|-------|------|-------------|---------------------|------------------------|
| 8B | 10 | 20% | 0 | 0 |
| 70B | 10 | 20% | 0 | 0 |

- 8B and 70B produce identical validated outputs.
- No invalid quotes; no JD echo after guardrails.

---

## 6. Recommendations

1. **Production model:** Use 8B for the match stage (cost, rate limits); keep 70B for extraction where possible.
2. **Always use frozen artifacts:** Avoid per-run extraction; lock requirements per JD.
3. **Monitor `invalid_quote_count`:** Non-zero values indicate guardrails catching bad evidence.
4. **Monitor `raw_vs_validated_delta`:** Non-zero values indicate the model attempted invalid matches.

---

## 7. Data Quality Notes

- `model_performance.csv` logs started including `jd_hash`, `requirements_source`, and `requirements_artifact_path` from ~17:55.
- `matched_count_raw`, `matched_count_validated`, `invalid_quote_count` added after quote-validation fix (not in historical CSV).
- Role titles: "AI Staff Software Engineer (Patient)" (Headway), "Senior Python Engineer" (sample JD, 355 chars).
