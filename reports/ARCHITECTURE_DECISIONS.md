# Architecture Decisions & Change Log

This document tracks design decisions, observed problems, and changes made to the RE Elicitation pipeline. Each entry explains **what** changed, **why**, and **what result** was observed or expected.

---

## Baseline Evaluation (2026-04-19)

### Datasets
- **NICE** — 15 projects, ~28 ground-truth requirements/project. Use-case descriptions were synthetically generated from the requirements (via `SYSTEM_USE_CASE_SYNTHESIS` prompt), making this a weaker elicitation benchmark. Better suited for FR/NFR classification evaluation.
- **PURE** — 15 real-world projects (law enforcement / civil RFPs), ~114 ground-truth requirements/project. Descriptions come from actual documents. Used as the **primary benchmark** for elicitation quality.

### Baseline Scores (single-agent vs multi-agent, existing outputs)

**PURE dataset** (primary benchmark):
| System | Coverage (Recall) | Precision | Semantic F1 | FR Coverage | NFR Coverage |
|---|---|---|---|---|---|
| single_agent | 0.359 | 0.367 | **0.338** | 0.352 | 0.186 |
| multi_agent_v1 | 0.329 | 0.375 | 0.325 | 0.317 | 0.210 |
| multi_agent_v2_sme | 0.260 | 0.300 | 0.258 | 0.254 | 0.085 |

**NICE dataset** (secondary benchmark):
| System | Coverage (Recall) | Precision | Semantic F1 | FR Coverage | NFR Coverage |
|---|---|---|---|---|---|
| single_agent | 0.497 | 0.384 | **0.420** | 0.647 | 0.302 |
| multi_agent_v1 | 0.424 | 0.308 | 0.348 | 0.573 | 0.230 |
| multi_agent_v2_sme | 0.327 | 0.209 | 0.246 | 0.465 | 0.176 |

Evaluation metric: semantic cosine similarity ≥ 0.6 using `sentence-transformers/all-MiniLM-L6-v2`.

### Key Observations
1. **Single agent outperforms both multi-agent variants** on both datasets.
2. **NFR coverage is the weakest metric across all systems** — 0.085 to 0.302. The extractor deprioritizes NFRs when generating a mixed list.
3. **PURE coverage drops significantly vs NICE** — PURE has ~114 reqs/project but the prompt caps generation at 50, structurally limiting recall.
4. **multi_agent_v2_sme is worst** despite being the most complex — the SME advisory adds LLM call overhead without improving output quality.

---

## Diagnosed Problems in Current Multi-Agent Architecture (v1 / v2)

### Problem 1: 50-requirement cap
- **Location:** `src/llm/prompts/re_elicitation_prompts.py` → `format_elicitation_prompt()` and `format_extractor_prompt()`
- **Impact:** PURE projects have ~114 ground-truth reqs. Generating only 50 means coverage is structurally capped at ~44% even with a perfect model.
- **Fix:** Remove the cap or raise it to 150.

### Problem 2: Budget runs out before revisions help
- **Location:** `src/llm/client.py` → `MAX_TOKENS_PER_TASK=20000`, `MAX_LLM_CALLS_PER_TASK=10`
- **Impact:** planner(1) + SME(1) + extractor(1) + critic(1) = 4 calls minimum. Token counting is also rough (`len(str) // 4`), hitting the budget prematurely and preventing useful critic revision loops.
- **Fix:** Increase token budget or remove it for RE elicitation; fix token counting.

### Problem 3: Critic approves too easily
- **Location:** `src/llm/prompts/re_elicitation_prompts.py` → `format_critic_prompt()`
- **Threshold:** "Approve if: ≥6 requirements, both FR and NFR present, no obvious functional area unaddressed."
- **Impact:** The extractor passes on the first attempt almost always, making the critic loop useless.
- **Fix:** Stricter threshold — check req count relative to description complexity, verify all NFR subtypes relevant to the domain are covered.

### Problem 4: Mixed-type extraction dilutes NFR coverage
- **Location:** `re_elicitation_extractor_node` — single call generates both FR and NFR together
- **Impact:** The model fills the 50-req budget with FRs and generates few NFRs. NFR coverage: 0.085–0.302.
- **Fix:** Separate FR and NFR extraction into parallel specialized calls.

### Problem 5: SME advisory adds overhead without measurable benefit
- **Location:** `re_sme_node` in v2 graph
- **Impact:** multi_agent_v2_sme scores _lower_ than v1 despite one extra LLM call. SME advice is generic and doesn't improve requirement specificity in practice.
- **Fix:** Either remove the SME node or fold its logic into the planner's system prompt as domain-awareness rather than a separate advisory call.

---

## Proposed Architecture — v3: Parallel Decomposed Extraction (Planned)

### Design

```
planner
   |
   +--[FR_extractor]--+
   |                  |--> merger + deduplicator --> critic --> [gap_filler?] --> finalize
   +--[NFR_extractor]-+
```

### Nodes

| Node | Role | Change from v2 |
|---|---|---|
| **planner** | Identifies domain, key quality attributes, functional areas | Absorbs SME domain-awareness; no separate SME call |
| **FR_extractor** | Generates functional requirements only, no cap | Replaces single mixed extractor |
| **NFR_extractor** | Generates NFRs across all 7 subtypes, no cap | New — directly fixes NFR coverage gap |
| **merger** | Combines FR + NFR lists, removes near-duplicates | New |
| **critic** | Stricter — checks req count + NFR subtype coverage | Stricter threshold |
| **gap_filler** (optional) | One targeted pass to address critic-identified gaps | Replaces open-ended revision loop |
| **finalize** | Writes `final_requirements` | Unchanged |

### Expected Improvements
- NFR coverage: from ~0.186 → target >0.35 (dedicated extractor forced to cover all subtypes)
- Overall coverage on PURE: from ~0.359 → target >0.45 (no req cap + parallel extraction)
- Fewer wasted LLM calls than v2 (no separate SME node)

### Files to create / modify
- `src/systems/multi_agent/nodes/re_elicitation_fr_extractor.py` — new
- `src/systems/multi_agent/nodes/re_elicitation_nfr_extractor.py` — new
- `src/systems/multi_agent/nodes/re_elicitation_merger.py` — new
- `src/systems/multi_agent/re_elicitation_graph_v3.py` — new graph wiring
- `src/llm/prompts/re_elicitation_prompts.py` — add FR-only and NFR-only prompt variants
- `scripts/run_re_elicitation.py` — register v3 system

---

## Changes Made

_Entries will be added here as implementation progresses._

| Date | File | Change | Reason |
|---|---|---|---|
| 2026-04-19 | — | Baseline evaluation run on NICE + PURE | Establish scores before any changes |
| 2026-04-19 | `reports/ARCHITECTURE_DECISIONS.md` | Created this document | Track decisions and rationale |
