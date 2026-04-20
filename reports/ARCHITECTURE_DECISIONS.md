# Architecture Decisions & Change Log

This document tracks **why** we made design choices, **what** we tested, **what** we observed, and **what** changes we made accordingly.

---

## Context: Course Project Goals

**Objective:** Improve LLM-based Requirements Elicitation (RE) — given a project use-case description, generate a comprehensive list of software requirements.

**Team Role:** Single-agent RE implementation and multi-agent architecture improvements.

**Primary Deliverables:**
1. Baseline evaluation of single-agent vs multi-agent systems
2. Identify performance bottlenecks
3. Propose and implement improved architecture (v3)
4. Document decisions and rationale

---

## Dataset Selection & Justification (2026-04-19)

### Why PURE instead of NICE?

**NICE Dataset:**
- 15 projects from NASA/DHS (PROMISE repository)
- ~28 ground-truth requirements per project
- **Problem:** Use-case descriptions were synthetically generated FROM the requirements (via Claude), making it circular — the model is evaluated on recovering requirements from descriptions derived from those very requirements
- **Verdict:** Good for FR/NFR classification, weak for elicitation evaluation

**PURE Dataset:**
- 15 real-world projects extracted from law enforcement and civil engineering RFPs
- Source: Ferrari et al., RE'17 (https://zenodo.org/records/1414117)
- Original dataset: 18 projects; we use the 15 with sufficient data quality
- ~114 ground-truth requirements per project (on average)
- **Advantage:** Actual project specifications, not reverse-engineered
- **Verdict:** Realistic, harder, better benchmark

**Decision:** Use **PURE as primary benchmark** (more realistic) and NICE as secondary (simpler baseline).

### Dataset Composition (PURE)

15 projects from diverse domains:

| Project ID | Domain | Requirements |
|---|---|---|
| 0000 - cctns | Law Enforcement (case management) | 114 |
| 0000 - gamma j | Engineering | 51 |
| 1995 - gemini | Government | 55 |
| 1998 - themas | Healthcare | 41 |
| 1999 - dii | Civil | 12 |
| 1999 - tcs | Transportation | 99 |
| 2003 - qheadache | Medical | 8 |
| 2005 - phin | Public Health | 49 |
| 2006 - eirene sys 15 | Railway | 247 |
| 2007-eirene_fun_7-2 | Railway | 583 |
| 2007-ertms | Railway | 198 |
| 2008 - keepass | Software Security | 32 |
| 2008 - peering | Networking | 20 |
| 2009 - peppol approved | E-Commerce | 61 |
| 2010-blitdraft | Defense | 54 |

**Why 15 not 18?** Original PURE has 18 projects. Our codebase filtered to 15 (likely by minimum requirement count for meaningful evaluation).

---

## Baseline Evaluation (2026-04-19)

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

**What this means:**
- Coverage = recall: what fraction of ground-truth requirements did we match?
- Precision: what fraction of generated requirements matched ground truth?
- F1: harmonic mean of both

### Key Observations & Surprises

1. **Single agent outperforms both multi-agent variants** on both datasets.
   - **Why surprising?** Multi-agent has planner + extractor + critic + retries; intuitively should be better
   - **Root cause:** Multi-agent complexity introduces overhead without benefit; critic approves too easily, revision loops don't trigger
   
2. **NFR coverage is the weakest metric everywhere** — 0.085 to 0.302 (vs FR coverage 0.25–0.65).
   - **Why?** When the model generates a mixed FR+NFR list with a 50-req cap, it prioritizes FRs (more concrete) and underweights NFRs
   - **Implication:** NFR-specific extraction needed

3. **PURE coverage is 30% lower than NICE** (0.359 vs 0.497 for single-agent).
   - **Why?** PURE has ~114 reqs/project but prompt caps generation at 50 → structurally impossible to exceed 44% coverage
   - **Root cause:** Hardcoded "up to 50 requirements" in prompt

4. **multi_agent_v2_sme is worst despite being most complex**.
   - **Why?** SME advisory adds one extra LLM call (cost) without improving output quality
   - **Verdict:** SME node is overhead, not signal

---

## Diagnosed Problems in Current Architecture

### Problem 1: 50-requirement cap
- **Location:** `src/llm/prompts/re_elicitation_prompts.py` lines 34-35 (single-agent) and ~72-73 (multi-agent extractor)
- **Code:** `"Generate up to 50 requirements..."`
- **Impact:** PURE projects have ~114 reqs. Cap = structurally impossible to exceed 44% coverage
- **Evidence:** Single-agent F1 0.338 on PURE (limited by cap) vs 0.420 on NICE (fewer reqs, cap less constraining)
- **Fix:** Change to "up to 150 requirements" or remove cap entirely

### Problem 2: Budget runs out before revision loops help
- **Location:** `src/llm/client.py` → `MAX_TOKENS_PER_TASK=20000`, `MAX_LLM_CALLS_PER_TASK=10`
- **Issue:** Rough token counting (`len(str) // 4`) + multi-agent graph needs ≥4 calls (planner, extractor, critic, feedback loop) = budget exhausted before useful revisions
- **Evidence:** Critic almost never triggers revision loop; budget rarely allows >1 revision
- **Fix:** Increase budget or disable for RE elicitation

### Problem 3: Critic threshold is too lenient
- **Location:** `src/llm/prompts/re_elicitation_prompts.py` → `format_critic_prompt()`
- **Threshold:** "Approve if: ≥6 requirements + both FR and NFR present + no obvious gap"
- **Issue:** Extractor always passes on first attempt; revision loop never activates
- **Evidence:** Multi-agent results show no improvement from revision attempts (critic never rejects)
- **Fix:** Stricter threshold — check req count relative to complexity, all NFR subtypes covered

### Problem 4: Mixed FR+NFR extraction dilutes NFR quality
- **Location:** `re_elicitation_extractor_node` makes one call for both types
- **Issue:** When budget is 50 reqs total, model biases towards FRs (more concrete), underweighting NFRs
- **Evidence:** NFR coverage 0.085–0.186 everywhere vs FR coverage 0.25–0.65
- **Fix:** Separate extractors — one for FR (no cap), one for NFR with explicit subtype targets

### Problem 5: SME advisory adds cost without signal
- **Location:** `re_sme_node` in v2
- **Issue:** Produces generic domain advice (e.g., "remember security is important") that doesn't improve output
- **Evidence:** v2_sme scores *lower* than v1 despite extra LLM call
- **Fix:** Remove or fold logic into planner system prompt

---

## Proposed Architecture — v3: Parallel Decomposed Extraction

### Why This Design?

**Root cause:** Single mixed extractor + weak critic loop = poor NFR coverage + wasted budget.

**Solution:** Parallel specialized extractors that don't compete for budget.

### Design

```
planner (identifies domain, key QAs, functional areas)
   |
   +--[FR_extractor]--+
   |  (FRs only)      |
   |                  |--> merger (deduplicate) --> stricter critic --> [gap_filler?] --> finalize
   |                  |
   +--[NFR_extractor]-+
      (NFRs only, all 7 subtypes explicitly covered)
```

### Key Changes from v2

| Node | v2 | v3 | Why |
|---|---|---|---|
| **planner** | identifies domain + strategy | same | works well |
| **SME node** | produces advisory | REMOVED | low ROI |
| **extractor** | mixed FR+NFR in one call | SPLIT → FR_extractor + NFR_extractor | no budget competition |
| **merger** | N/A | NEW | combines FR + NFR lists |
| **critic** | lenient (≥6 reqs + both types) | stricter (req count relative to description, all NFR subtypes) | actually trigger revisions |
| **gap_filler** | N/A | new optional node | targeted revision vs open-ended retry |
| **req cap** | 50 | NONE per extractor | no structural ceiling |

### Expected Improvements

- **NFR coverage:** 0.186 → target >0.35 (dedicated extractor forced to cover all 7 subtypes)
- **Overall coverage:** 0.359 → target >0.45 (no cap + parallel extraction)
- **LLM efficiency:** fewer wasted calls (no failed revision loops)

---

## Model Comparison: Claude vs Local Ollama (2026-04-19)

### Why Compare?

Course constraint: may not have API budget for large-scale runs. Need to know if local Ollama is viable fallback.

### Single-Agent Performance on PURE Dataset

| Model | Size | Coverage | Precision | F1 | NFR Coverage |
|---|---|---|---|---|---|
| Claude Sonnet 4.6 | ~100B | 0.359 | 0.367 | **0.338** | 0.186 |
| Mistral-Nemo 12B | 12B | 0.285 | 0.288 | **0.263** | 0.071 |

**Gap:** ~20% lower for mistral-nemo (F1 0.263 vs 0.338)

**Why the gap?**
- Model capacity: 12B vs 100B+
- Mistral-nemo not optimized for structured output (uses JSON parsing fallback)
- Weaker reasoning on domain-specific patterns

**Conclusion:**
- **Production/final evaluation:** Use Claude Sonnet
- **Local development/testing:** Mistral-nemo acceptable with known quality loss

---

## Changes Made

_Tracking all modifications for reproducibility._

| Date | File(s) | Change | Reasoning | Impact |
|---|---|---|---|---|
| 2026-04-19 | — | Baseline eval: Claude on NICE + PURE | Establish baseline before changes | Confirmed single > multi; identified cap + NFR problems |
| 2026-04-19 | 10 scripts | Fix Windows Unicode (→ → ->) | UnicodeEncodeError on Windows | Allows eval scripts to complete |
| 2026-04-19 | — | Verify Ollama integration | Mistral-nemo option for local dev | Confirmed viable with 20% quality tradeoff |
| 2026-04-19 | `ARCHITECTURE_DECISIONS.md` | Created this document | Track decisions + evidence | Living reference for project history |
| 2026-04-20 | `ARCHITECTURE_DECISIONS.md` | Add context, dataset justification, problem analysis | Full traceability from observation → diagnosis → fix | Supports future work / paper writing |

---

## Next Steps (Planned)

1. **Quick win:** Remove 50-req cap in prompt (easy, should boost both single + multi ~5-10% F1)
2. **Implement v3 multi-agent:** FR + NFR extractors, stricter critic
3. **Evaluate v3:** Compare v3 vs baseline on PURE
4. **Document results:** Update this file with v3 scores + analysis

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

## Model Comparison: Claude vs Local Ollama (2026-04-19)

### Single-Agent Performance on PURE Dataset

| Model | Size | Coverage | Precision | F1 | NFR Coverage |
|---|---|---|---|---|---|
| Claude Sonnet 4.6 | ~100B (est.) | 0.359 | 0.367 | **0.338** | 0.186 |
| Mistral-Nemo 12B | 12B | 0.285 | 0.288 | **0.263** | 0.071 |

**Gap:** Mistral-nemo scores ~20% lower (F1 0.263 vs 0.338). Likely due to:
- Smaller model capacity (12B vs 100B+)
- Less optimized for structured output
- Weaker reasoning on domain-specific patterns

**Conclusion:** Claude Sonnet is production-grade; mistral-nemo is adequate for local dev/testing but with measurable quality loss.

---

## Changes Made

_Entries will be added here as implementation progresses._

| Date | File | Change | Reason |
|---|---|---|---|
| 2026-04-19 | — | Baseline evaluation run on NICE + PURE with Claude | Establish scores before any changes |
| 2026-04-19 | `reports/ARCHITECTURE_DECISIONS.md` | Created this document | Track decisions and rationale |
| 2026-04-19 | 10 scripts | Fix Windows Unicode encoding (→ to ->) | UnicodeEncodeError on Windows in print statements |
| 2026-04-19 | — | Pilot run: mistral-nemo on 3 PURE projects | Verify Ollama integration works |
| 2026-04-19 | — | Full run: mistral-nemo on 15 PURE projects | Benchmark local model against Claude baseline |
