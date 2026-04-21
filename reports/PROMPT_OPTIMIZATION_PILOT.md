# Prompt Optimization Pilot: Results & Recommendations

**Date**: 2026-04-21  
**Project**: 1995 - Gemini (Telescope Control Software)  
**Ground Truth**: 55 requirements (54 FR, 1 NFR = 98% FR)

## Objective

Test 3 prompt variations to improve RE elicitation quality on the Gemini project, which currently has:
- Generated: 50 requirements (30 FR, 20 NFR = 60% FR)
- Issue: Claude hallucinates 20 NFRs when only 1 exists
- Opportunity: Better prompt guidance could improve FR/NFR ratio and increase requirement count

## Three Prompt Variations

### Prompt 1: Original (Baseline)
```
"Generate a comprehensive list of requirements from this use case (up to 50).
Cover all major functional areas and non-functional concerns.
Output valid JSON only."
```
**Expected**: 50 reqs, 60% FR (same as current)

### Prompt 2: Strict NFR Guidance
```
"Extract requirements from this use case.
CRITICAL: Only generate NFRs if explicitly mentioned. Do NOT invent them.
Rule: Only NFR if use case mentions: performance, security, reliability, compliance, availability.
Do NOT invent NFRs (e.g., don't add 'secure' to every FR).
If unsure, classify as FR.
Generate 50-60 requirements."
```
**Expected Improvement**:
- Better FR/NFR ratio (closer to 98% FR)
- Fewer hallucinated NFRs
- Same or slightly more requirements

### Prompt 3: Feature-Based Decomposition
```
"Identify major features from this use case, then generate 3-5 specific requirements per feature.
Be specific: don't say 'system shall manage X', say 'system shall create, read, update, delete X records'.
Only add NFRs if explicitly mentioned.
Generate 55-70 requirements."
```
**Expected Improvement**:
- More requirements (55-70 vs 50)
- More granular, specific requirements
- Better coverage of functionality
- Still maintains low NFR count

## Key Insights from Analysis

### Problem 1: Hallucinated NFRs
Current state: Claude generates 48% NFRs when only 4% should be NFR
- Claude treats every quality attribute as a separate NFR
- "System shall manage inventory" becomes:
  - "System shall manage inventory" (FR)
  - "System shall manage inventory securely" (NFR: security)
  - "System shall manage inventory efficiently" (NFR: performance)

**Solution**: Explicitly tell Claude to extract NFRs only if mentioned in use case, not infer them.

### Problem 2: Requirement Cap Too Low
Current: 50 requirement cap, but ground truth averages 108
- Projects with 50-80 GT reqs hit the cap
- Larger projects (100+ GT reqs) have max 44% coverage

**Solution**: Increase cap to 60-70 with Prompt 2/3 guidance.

### Problem 3: Granularity Mismatch
Current: Requirements are too high-level and generic
- Generated: "System shall manage criminal cases" (1 requirement)
- Ground truth: "System shall create case records", "System shall update case records", "System shall search for cases", "System shall link evidence to cases" (4 specific requirements)

**Solution**: Use feature-based approach (Prompt 3) to break features into specific, testable requirements.

## Recommended Testing Plan

### Phase 1: Baseline (Already Done)
- ✓ Claude single-agent: F1 = 0.353
- ✓ Ollama/Mistral: F1 = 0.338

### Phase 2: Prompt Optimization (Blocked by API Issues)
- [ ] Test Prompt 2 on Gemini: Expect FR/NFR ratio improvement (< 10% NFR)
- [ ] Test Prompt 3 on Gemini: Expect 55-70 requirements, better coverage
- [ ] Re-run evaluation on 5-project pilot with winning prompt
- [ ] Compare metrics: F1 should improve by 10-15%

### Phase 3: Full Dataset (If improvements show)
- [ ] Run winning prompt on all 15 projects
- [ ] Measure consistency across project types
- [ ] Check if improvements hold or vary by domain

## Expected Outcomes

If Prompt 2 works:
- FR/NFR ratio improves from 60% to ~95% FR (closer to GT's 98%)
- Requirement count: 50-60 (might increase slightly)
- F1 score: +5-10% improvement

If Prompt 3 works:
- FR/NFR ratio improves to ~95% FR
- Requirement count: 55-70 (significant increase)
- F1 score: +10-15% improvement
- Coverage: Should improve from 0.390 to ~0.45+

## Implementation Strategy

Once Claude API is fixed:

```python
# Update src/llm/prompts/re_elicitation_prompts.py

def format_elicitation_prompt(use_case: str) -> str:
    return (
        f"Given this use case, extract software requirements.\n\n"
        f"USE CASE:\n{use_case}\n\n"
        f"Return JSON with 'requirements' array:\n"
        f"- req_id, text, type (FR/NFR), nfr_subtype, source, rationale\n\n"
        f"CRITICAL RULES:\n"
        f"1. Extract all FUNCTIONAL requirements mentioned or clearly implied\n"
        f"2. Only include NFR if the use case explicitly mentions:\n"
        f"   performance, security, reliability, compliance, availability, scalability\n"
        f"3. Do NOT invent NFRs (e.g., don't add 'secure' to every FR)\n"
        f"4. If unsure, classify as FR\n"
        f"5. For each feature, generate multiple specific requirements:\n"
        f"   Instead of: 'System shall manage users'\n"
        f"   Generate: 'System shall create user accounts', "
        f"'System shall authenticate users', 'System shall manage user permissions'\n\n"
        f"Generate 60-70 detailed requirements."
    )
```

## Blockers

### Claude API Structured Output Bug
- Error: `'str' object has no attribute 'model_dump'`
- Cause: Unknown (likely langchain-anthropic v1.4.0 compatibility issue)
- Impact: Cannot test with Claude (best model for this task)
- Solution: Regenerate API key or downgrade langchain-anthropic

### Ollama Schema Mismatch
- Ollama returns different field names (id, description vs req_id, text)
- Would need to retrain or create custom parser
- Not practical for quick testing

## Recommendation

1. **Fix Claude API** (priority 1)
   - Regenerate ANTHROPIC_API_KEY
   - Test if new key fixes structured output issue
   - If not: downgrade langchain-anthropic to 1.3.x

2. **Once Claude works**
   - Run Prompt 2 (Strict NFR) on Gemini
   - If FR/NFR ratio improves: adopt it
   - Then test Prompt 3 (Feature-based)
   - Compare metrics

3. **If both work**
   - Roll out better prompt to full 15-project dataset
   - Measure improvement across all projects
   - Update documentation

## Expected Impact

Using Prompt 2 or 3 alone could improve F1 score from **0.353 to 0.40-0.42** (10-15% improvement).

Combined with:
- Increasing requirement cap to 70-80
- Better NFR guidance
- Feature-based decomposition

Could reach **F1 = 0.45+** (30% improvement over current).

