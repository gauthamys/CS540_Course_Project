# Prompt Optimization Pilot: Results & Recommendations

**Dataset**: PURE (15 projects, pilot = first 5)
**System**: Single Agent (Claude claude-sonnet-4-6)
**Evaluation**: Semantic cosine similarity, threshold = 0.6

---

## Problem Analysis (Pre-Optimization)

**Baseline scores (5-project pilot, old prompt):**
- Coverage (recall): 0.305
- Precision: 0.323
- Semantic F1: 0.304
- Avg requirements generated: 44.8

### Three root causes identified:

**1. Cap too low**
- Old prompt: "Generate up to 50 requirements"
- Ground truth averages 108 reqs/project (max 583 for eirene_fun_7-2)
- At 50 reqs, coverage on large projects is physically capped (e.g. cctns: 50/114 = 44% theoretical max)

**2. Claude stopped early**
- "Up to 50" lets Claude stop whenever it wants
- themas generated only 24 requirements against 41 GT → wasted capacity

**3. Requirements too generic**
- Claude wrote "system shall manage X" (1 req) instead of "create X", "update X", "delete X", "search X" (4 reqs)
- Ground truth uses granular, operation-level requirements
- This causes semantic mismatch — the generated text doesn't match the GT text closely enough

**4. NFR hallucination (minor)**
- Old system prompt encouraged NFR generation; GT datasets are ~95%+ FR
- Generated NFRs that don't exist in GT dilute precision slightly

---

## Changes Made (2026-04-21)

### 1. System prompt (`SYSTEM_RE_ELICITATION`)

**Before:**
```
"You are a senior requirements engineer. You produce structured, unambiguous software requirements.
Classify each requirement as FR (functional) or NFR (non-functional). For NFR, add the most specific
subtype from: performance, security, usability, reliability, maintainability, portability, availability.
Use 'other' only if none fit. Output valid JSON only."
```

**After:**
```
"You are a senior requirements engineer. You extract precise, testable software requirements from use
case descriptions. Classify each requirement as FR (functional) or NFR (non-functional).
CRITICAL: Only classify as NFR if the use case explicitly mentions a quality concern (e.g. performance,
security, reliability, compliance, availability, scalability). Do NOT invent NFRs — if unsure, classify
as FR. For NFR, add the most specific subtype from: performance, security, usability, reliability,
maintainability, portability, availability. Output valid JSON only."
```

**Why:** Removes the implicit encouragement to generate NFRs. Now only generates them when the use case actually mentions quality concerns.

### 2. User prompt (`format_elicitation_prompt()`)

**Key changes:**
- Added explicit feature decomposition instruction with a concrete example
- Added "cover create, read, update, delete, search, validate operations where applicable"
- Changed cap from "up to 50" to "between 60 and 80 — do not stop early, be exhaustive"
- Added strict NFR rule reinforcement

**Before:** Vague "be comprehensive, up to 50"

**After:** Structured instructions with example of granular decomposition + floor of 60 reqs

---

## Results (2026-04-21, 5-project pilot)

| Metric | Before | After | Change |
|---|---|---|---|
| Coverage (recall) | 0.305 | **0.405** | **+33%** |
| Precision | 0.323 | **0.385** | **+19%** |
| Semantic F1 | 0.304 | **0.381** | **+25%** |
| FR coverage | 0.301 | **0.400** | **+33%** |
| NFR coverage | 0.074 | 0.074 | no change |
| Avg reqs generated | 44.8 | **76.0** | +70% |

**Results file**: `outputs/re_elicitation_pure/single_agent/results_claude_2026-04-21_19-57.jsonl`

### Why NFR coverage didn't improve
NFR coverage stays near zero because the GT NFRs are highly specific domain phrases (e.g. "system shall provide context-sensitive help material"). Our generated NFRs, even when present, rarely match those specific texts at cosine sim ≥ 0.6. This is a harder problem than FR coverage and would require domain-specific prompting or a multi-pass approach.

---

---

## Prompt v3 — Structured RE Analysis (Actor / Entity / Process)

**Date:** 2026-04-21 | **Results file:** `outputs/re_elicitation_pure/single_agent/results_claude_2026-04-21_20-23.jsonl`

### Changes from v2

Restructured user prompt into three explicit passes mirroring real RE methodology:

- **STEP 1 — ACTORS**: For every actor/role named, generate complete workflow requirements using exact actor names from the use case.
- **STEP 2 — DATA ENTITIES**: For every data object or record type named, generate CRUD operations using exact entity names.
- **STEP 3 — PROCESSES & WORKFLOWS**: For every process or system behaviour described, generate step-by-step requirements including error handling, validation, and notifications where implied.

Added: *"Use the exact terminology and names from the use case — do not paraphrase."*

**Rationale:** Real REs analyse actors, entities, and processes systematically before writing. Using exact vocabulary from the use case improves semantic similarity to GT since both derive from the same domain language.

### Bug fixed

`DEFAULT_MAX_TOKENS=8192` too low for 75-80 reqs × 6 fields. themas hit the limit mid-JSON, causing a Pydantic validation error. Agent retried automatically (2 calls, recovered). Fixed by raising `DEFAULT_MAX_TOKENS` 8192 → 16384 in `src/llm/client.py`.

### Results

| Metric | v1 (baseline) | v2 | v3 | v1→v3 |
|---|---|---|---|---|
| Coverage | 0.305 | 0.405 | 0.394 | **+29%** |
| Precision | 0.323 | 0.385 | **0.405** | **+25%** |
| Semantic F1 | 0.304 | 0.381 | **0.391** | **+29%** |
| Avg reqs | 44.8 | 76.0 | 76.2 | +70% |

v2 vs v3 is within noise (std dev ~0.20). v3 trades small coverage drop for better precision — marginally better F1. **v3 is the current live prompt.**

### Per-project (v3)

| Project | GT Reqs | Generated | Coverage | Precision | F1 |
|---|---|---|---|---|---|
| 0000 - cctns | 114 | 75 | 0.272 | 0.507 | 0.354 |
| 0000 - gamma j | 51 | 75 | 0.275 | 0.293 | 0.284 |
| 1995 - gemini | 55 | 78 | 0.527 | 0.513 | 0.520 |
| 1998 - themas | 41 | 75 | 0.610 | 0.493 | 0.545 |
| 1999 - dii | 12 | 78 | 0.083 | 0.128 | 0.101 |

dii (12 GT reqs, 78 generated) tanks precision — 83% of what we generated has no GT match. This project alone pulls the average down significantly.

---

## Ceiling Analysis

Getting to F1=0.70 is not achievable with a single-call, use-case-only approach:

- **Large projects**: eirene_fun_7-2 has 583 GT reqs. At 75 generated reqs, theoretical max coverage = 12.9%. This one project alone prevents the average from reaching 70%.
- **Small projects**: dii has 12 GT reqs. Generating 78 reqs means max precision ≈ 15%.
- **Information gap**: GT reqs were written from full specification documents. The use case is a compressed 3-6 sentence summary — we cannot recover the original spec's domain-specific phrasing from it.

**Realistic ceiling: F1 ≈ 0.40–0.45**

---

## Next Steps

- [ ] Run v3 on full 15-project dataset and compare single_agent vs multi_agent_v1 (F1=0.325)
- [ ] If v3 single_agent > multi_agent_v1 on 15 projects, adopt as new single-agent baseline
- [ ] Consider adaptive output size: detect small projects (short use case / few entities) and lower the cap to ~30-40 reqs to avoid precision collapse
- [ ] Run same prompt on local LLM (Mistral-Nemo) to see if gains transfer
