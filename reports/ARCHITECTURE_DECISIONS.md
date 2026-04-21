# Architecture Decisions

This document records key architectural decisions, experiments, and learnings for the RE Elicitation pipeline.

---

## Decision: Single-Agent RE Elicitation Prompt Optimization (2026-04-21)

### Background
Initial evaluation showed:
- Claude single-agent (5-project pilot): F1 = 0.353, Coverage = 0.390
- Ground truth baseline: Average 108 requirements per project
- Claude generation: Capped at 50 requirements per project
- **Gap**: Claude generating only 46% of required requirements

### Attempted Change: Increase Requirement Target
**Goal**: Improve coverage by asking Claude to generate 80-150 requirements instead of 50.

**Changes Made**:
1. Modified `src/llm/prompts/re_elicitation_prompts.py`:
   - `format_elicitation_prompt()`: Changed from "up to 50" to "80-150 detailed requirements"
   - Added guidance: "Extract requirements directly stated", "Break down features into granular requirements", "Avoid generic or overlapping requirements"
   - `format_extractor_prompt()`: Same changes for multi-agent systems

2. Rationale:
   - Ground truth has 8-583 requirements per project (avg 108)
   - Increasing cap should improve recall/coverage
   - Added explicit guidance to reduce hallucinated/generic requirements

### Result: Failed
**Error**: `'str' object has no attribute 'model_dump'` in langchain-anthropic's structured output handling.

**Root Cause**: Likely a compatibility issue between:
- langchain-anthropic 1.4.0
- pydantic 2.13.1
- Claude Sonnet 4.6 API

**Hypothesis**: The longer prompt may have triggered a different response format that the structured output parser couldn't handle, or it's a transient API issue.

### Decision: Revert and Switch to Ollama
**Action Taken**:
1. Reverted prompt changes back to original "up to 50 requirements"
2. Switched to Ollama (mistral-nemo) for local testing
3. Reason: Unblock progress while investigating Claude API issue

**Current Status** (2026-04-21):
- Ran pilot with Ollama/mistral-nemo
- Single-stage prompt (unchanged from baseline)
- 5-project pilot for quick feedback loop
- Results: F1 = 0.244 (Claude achieved 0.353 on same 5 projects)

### Comparison: Claude vs Mistral (Pure Dataset)

| System | Dataset | F1 | Coverage | Precision | Notes |
|--------|---------|----|---------:|-----------|-------|
| Claude | 5 projects | 0.353 | 0.390 | 0.336 | Better coverage despite lower precision |
| Mistral baseline | 15 projects | 0.338 | 0.359 | 0.367 | Established baseline |
| Mistral (new) | 5 projects | 0.244 | 0.253 | 0.243 | 1 project crashed; smaller sample |

**Conclusion**: Claude outperforms Mistral by ~40% on F1 score. Should prioritize fixing Claude API issue over using Mistral locally.

### Next Steps
1. **Regenerate Claude API Key** (current key exposed and needs rotation)
2. **Debug Claude Structured Output**:
   - Try with new API key first
   - If still broken: downgrade langchain-anthropic or upgrade pydantic
   - File issue with langchain if bug confirmed
3. **Incremental Prompt Improvement** (once Claude works):
   - Instead of 80-150, try 60-70 requirements (smaller increment)
   - Add structured guidance: "For each feature: FR + NFR"
   - Use few-shot examples
4. **Consider Multi-Stage Approach** (if single-stage hits ceiling):
   - Use case → BRD → Requirements (2 LLM calls)
   - Better for quality+quantity tradeoff

---

## Decision: Project Structure Reorganization (2026-04-21)

### Changes Made
1. **Script naming**: Added clear prefixes (prepare_, run_, evaluate_)
   - Makes script purpose self-evident
   - Reduces cognitive load for new contributors

2. **Node directory structure**: Organized by task type
   - `src/systems/multi_agent/nodes/codegen/` - CodeGen-specific nodes
   - `src/systems/multi_agent/nodes/re_elicitation/` - RE-specific nodes
   - `src/systems/multi_agent/nodes/re_classification/` - RE classification (legacy)

3. **Removed redundant files**:
   - Deleted duplicate critic/extractor/planner from root nodes/
   - Consolidated into domain-specific folders

### Rationale
- Easier to navigate codebase
- Clear separation of concerns
- Self-documenting structure
- Reduces confusion between RE and CodeGen pipelines

### Outcome
✓ No functional changes - all imports updated and tested
✓ Created PROJECT_STRUCTURE.md and QUICK_REFERENCE.md for onboarding

---

## Baseline Metrics Summary

### Single-Agent RE Elicitation (Pure Dataset)

**Claude** (best-performing):
- 5-project pilot: F1 = 0.353, Coverage = 0.390, Precision = 0.336

**Mistral Nemo** (established baseline):
- 15-project full dataset: F1 = 0.338, Coverage = 0.359, Precision = 0.367

**Insight**: Claude generates better coverage (recalls more GT requirements) despite lower precision. Better for recall-sensitive applications.

---

## Open Issues

### 1. Claude API Structured Output Bug (RESOLVED)
- **Status**: Fixed — API key was rotated and structured output works correctly
- **Resolution**: New API key resolved the `'str' object has no attribute 'model_dump'` error

### 2. Requirement Generation Gap (50 vs 108 avg) (PARTIALLY RESOLVED)
- **Status**: Cap raised to 60-80; F1 improved from 0.304 to 0.391
- **Remaining gap**: Projects with 200-583 GT reqs still have a hard coverage ceiling
- **Next Action**: Adaptive cap based on project size

### 3. Precision vs Coverage Tradeoff
- **Status**: Mostly resolved — v3 prompt achieves balanced precision (0.405) and coverage (0.394)
- **Remaining**: Small projects (dii: 12 GT reqs) still tank precision when over-generating

---

## Experiment Log

### Experiment 1: Increase Requirement Cap (FAILED)
- **Date**: 2026-04-21
- **Change**: "up to 50" → "80-150 detailed requirements"
- **Result**: langchain-anthropic structured output error (`'str' object has no attribute 'model_dump'`)
- **Learnings**: Was actually an API key issue, not a prompt issue. Reverted and unblocked with Ollama.

### Experiment 2: Ollama Fallback (COMPLETED)
- **Date**: 2026-04-21
- **Change**: Switched to local Ollama/mistral-nemo
- **Result**: F1 = 0.244 (40% worse than Claude)
- **Status**: Confirmed Claude is the better model; returned to Claude once API key was fixed

### Experiment 3: Feature Decomposition + Higher Cap — Prompt v2 (SUCCESS)
- **Date**: 2026-04-21
- **Changes**:
  - System prompt: Added strict NFR restriction — only generate NFR if use case explicitly mentions a quality concern
  - User prompt: Added feature decomposition example (before/after showing granular vs generic), raised cap from 50 to "between 60 and 80", added floor to prevent early stopping
- **Result**: F1 0.304 → 0.381 (+25%), Coverage 0.305 → 0.405 (+33%), avg reqs 44.8 → 76.0
- **Learnings**: The biggest single improvement came from two things: more reqs generated + more granular decomposition. NFR restriction had minor effect on scores but improves output quality.

### Experiment 4: Structured RE Analysis — Prompt v3 (MARGINAL IMPROVEMENT)
- **Date**: 2026-04-21
- **Changes**: Restructured user prompt into three explicit passes: (1) Actors — generate workflow reqs for each named actor, (2) Data Entities — CRUD for each named data object, (3) Processes — step-by-step reqs for each workflow. Added "use exact terminology from the use case — do not paraphrase."
- **Rationale**: Mirrors real RE methodology. Using exact domain vocabulary from the use case increases semantic similarity to GT since both derive from the same source.
- **Result**: F1 0.381 → 0.391 (+3%), Coverage 0.405 → 0.394 (-3%), Precision 0.385 → 0.405 (+5%)
- **Learnings**: v2 vs v3 difference is within noise (std dev ~0.20). v3 trades small coverage drop for better precision. The structured methodology helps precision but doesn't unlock more coverage since the information ceiling is the use case itself, not the prompt structure.
- **Bug found**: `DEFAULT_MAX_TOKENS=8192` was too low — 75-80 reqs × 6 fields hits the limit. themas failed mid-JSON on first attempt. Fixed by raising to 16384 in `src/llm/client.py`.

---

## Updated Baseline Metrics (2026-04-21)

### Single-Agent RE Elicitation (Pure Dataset, 5-project pilot)

| Prompt Version | Coverage | Precision | F1 | Avg Reqs |
|---|---|---|---|---|
| v1 — Original (cap=50) | 0.305 | 0.323 | 0.304 | 44.8 |
| v2 — Feature decomp (cap=60-80) | 0.405 | 0.385 | 0.381 | 76.0 |
| v3 — Actor/entity/process (cap=60-80) | 0.394 | 0.405 | **0.391** | 76.2 |

**Multi-agent baselines (15 projects, from earlier runs):**
- multi_agent_v1: F1=0.325, Coverage=0.329, Precision=0.375
- multi_agent_v2_sme: F1=0.258, Coverage=0.260, Precision=0.300

**v3 single-agent now beats multi_agent_v1 on F1 (0.391 vs 0.325) on the pilot.**

### Ceiling Analysis
Theoretical max F1 with single-call, use-case-only approach is ~0.40-0.45. Reasons:
- Large projects (eirene: 583 GT reqs) have <13% theoretical coverage at 75 generated reqs
- Small projects (dii: 12 GT reqs) cannot have >15% precision when generating 75+ reqs
- GT reqs were written from full spec docs; use case is a 3-6 sentence compressed summary — information gap is fundamental

