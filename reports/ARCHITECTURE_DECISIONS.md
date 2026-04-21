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

### 1. Claude API Structured Output Bug (CRITICAL)
- **Status**: Under investigation
- **Impact**: Cannot run Claude experiments
- **Workaround**: Use Ollama (performs 40% worse)
- **Action Required**: Regenerate API key, test with new key
- **Priority**: HIGH

### 2. Requirement Generation Gap (50 vs 108 avg)
- **Status**: Attempted to fix (see "Increase Requirement Target" above)
- **Impact**: Max coverage ~40% (generating only 50 of 108 req avg)
- **Next Action**: Try incremental increases (60, 70, 80) once Claude is fixed
- **Priority**: HIGH (ceiling on improvement)

### 3. Precision vs Coverage Tradeoff
- **Status**: Ongoing analysis
- **Observation**: More requirements → better coverage, potentially worse precision
- **Strategy**: Use structured prompts/multi-stage BRD approach
- **Priority**: MEDIUM

---

## Experiment Log

### Experiment 1: Increase Requirement Cap (FAILED)
- **Date**: 2026-04-21
- **Change**: "up to 50" → "80-150 detailed requirements"
- **Result**: langchain-anthropic structured output error
- **Learnings**: Large prompt changes can break structured output; need incremental approach
- **Next**: Try smaller increases (60-70)

### Experiment 2: Ollama Fallback (COMPLETED)
- **Date**: 2026-04-21
- **Change**: Switched to local Ollama/mistral-nemo
- **Result**: F1 = 0.244 (40% worse than Claude)
- **Status**: Unblocked pipeline, confirms Claude is better model
- **Next**: Fix Claude and return to it as primary

