# RE Elicitation Results — Multi-Agent Software Development Assistant

**Dataset:** NICE PROMISE-relabeled (15 projects, 622 ground-truth requirements)  
**Model:** `claude-sonnet-4-6`, `temperature=0`  
**Evaluation:** Semantic cosine similarity via `all-MiniLM-L6-v2`, threshold = 0.60  
**Date:** 2026-04-15

---

## 1. Summary Table

| System | Coverage (Recall) | Precision | Semantic F1 | FR Coverage | NFR Coverage | Avg Reqs/Project | Avg LLM Calls | Avg Tokens/Task | Total Tokens |
|---|---|---|---|---|---|---|---|---|---|
| Single-Agent | **0.402 ± 0.118** | **0.479 ± 0.094** | **0.426 ± 0.091** | **0.529** | **0.239** | 19.1 | 1.0 | 2,402 | 36,036 |
| Multi-Agent V1 | 0.334 ± 0.087 | 0.390 ± 0.094 | 0.348 ± 0.064 | 0.486 | 0.160 | 20.0 | 3.0 | 5,460 | 81,899 |
| Multi-Agent V2 (SME) | 0.358 ± 0.100 | 0.328 ± 0.100 | 0.330 ± 0.074 | 0.525 | 0.189 | 28.8 | 4.0 | 10,373 | 155,597 |

Ground truth: 622 requirements across 15 projects.

---

## 2. Metric Definitions

- **Coverage (Recall):** Fraction of ground-truth requirements for which at least one generated requirement has cosine similarity ≥ 0.60 to it.
- **Precision:** Fraction of generated requirements that have cosine similarity ≥ 0.60 to at least one ground-truth requirement.
- **Semantic F1:** Harmonic mean of coverage and precision.
- **FR Coverage / NFR Coverage:** Coverage computed separately for Functional and Non-Functional requirements.

---

## 3. Quality Comparison

### Semantic F1

| System | Semantic F1 | Δ vs Single-Agent |
|---|---|---|
| Single-Agent | **0.426** | — |
| Multi-Agent V1 | 0.348 | −0.078 (−18%) |
| Multi-Agent V2 (SME) | 0.330 | −0.096 (−23%) |

Single-Agent achieves the best Semantic F1. Both multi-agent systems underperform the single-shot baseline on all three metrics.

### FR vs NFR Coverage

All systems cover Functional Requirements substantially better than Non-Functional Requirements:

| System | FR Coverage | NFR Coverage | Gap |
|---|---|---|---|
| Single-Agent | 0.529 | 0.239 | 0.290 |
| Multi-Agent V2 (SME) | 0.525 | 0.189 | 0.336 |
| Multi-Agent V1 | 0.486 | 0.160 | 0.326 |

The SME node in V2 was designed to improve NFR coverage by adopting a domain-expert persona. It does improve NFR coverage relative to V1 (0.189 vs 0.160), but the improvement is modest and precision suffers as a result.

---

## 4. Orchestration Cost

### LLM Calls per Project

| System | Avg Calls | Multiplier vs Single-Agent |
|---|---|---|
| Single-Agent | 1.0 | 1× |
| Multi-Agent V1 | 3.0 | 3× |
| Multi-Agent V2 (SME) | 4.0 | 4× |

Multi-Agent V1 uses exactly 3 calls per project (Planner + Extractor + Critic) — the critic approved all 15 projects on first pass, so no revision loops were triggered. V2 adds a 4th call for the SME node. The Combiner node makes no LLM call (pure embedding-based deduplication).

### Tokens per Task

| System | Avg Tokens | Multiplier vs Single-Agent | Total Tokens |
|---|---|---|---|
| Single-Agent | 2,402 | 1× | 36,036 |
| Multi-Agent V1 | 5,460 | 2.3× | 81,899 |
| Multi-Agent V2 (SME) | 10,373 | 4.3× | 155,597 |

V2 uses 4.3× more tokens than Single-Agent per project. The SME node's dynamically constructed system prompt (domain + persona) and the combiner's larger combined requirement list passed to the critic account for the additional overhead.

---

## 5. Quality vs Cost Trade-off

Single-Agent produces the best Semantic F1 at the lowest cost. The multi-agent systems pay 3–4× in LLM calls and 2.3–4.3× in tokens for *lower* quality on this task.

| System | Semantic F1 | Total Tokens | F1 per 1K Tokens |
|---|---|---|---|
| Single-Agent | 0.426 | 36,036 | 0.0118 |
| Multi-Agent V1 | 0.348 | 81,899 | 0.0043 |
| Multi-Agent V2 (SME) | 0.330 | 155,597 | 0.0021 |

Single-Agent is **5.6× more token-efficient** than V2 on this task.

---

## 6. Key Finding: Single-Agent Wins on RE Elicitation

Unlike Code Generation (where both single-agent and multi-agent V1 achieved 100% pass@1), RE Elicitation shows a clear ranking: **simpler is better**.

**Why the multi-agent systems underperform:**

1. **Planner constrains the extractor.** The Planner node produces a strategy and a fixed list of key quality attributes. This narrows the Extractor's focus — useful for correctness on well-specified tasks, but harmful for open-ended elicitation where breadth matters.

2. **Critic approves too readily.** The Critic approved all 15 projects on first pass across both V1 and V2 — no revision loops ran at all. This means the multi-agent overhead of planner + critic adds cost with no quality benefit when the baseline output is already "good enough" by the critic's assessment.

3. **SME precision penalty.** V2 generates 28.8 requirements/project vs V1's 20.0 and Single-Agent's 19.1. More generated requirements improve recall marginally (+0.024 vs V1) but hurt precision significantly (−0.062 vs V1), yielding a lower F1 overall.

4. **Single-agent generates more freely.** With no planner constraining it and no structured output schema beyond the final list, the single-agent prompt elicits a broader, more natural set of requirements that aligns better with the ground truth's diversity.

---

## 7. Cost Summary

| System | Total Tokens | Est. Cost @ claude-sonnet-4-6 |
|---|---|---|
| Single-Agent | 36,036 | ~$0.11 |
| Multi-Agent V1 | 81,899 | ~$0.25 |
| Multi-Agent V2 (SME) | 155,597 | ~$0.47 |
| **Total** | **273,532** | **~$0.83** |

---

## 8. Dataset Notes

- **15 projects** from the NICE PROMISE-relabeled dataset (projects with ≥ 4 requirements)
- **622 total ground-truth requirements** (mix of FR, NFR, and NONE labels)
- **Use-case descriptions** were synthesized by Claude from each project's requirements (offline preprocessing via `prepare_re_elicitation.py`), then used as input to all three systems — ensuring a fair, identical input across systems
- **Ground-truth split:** NICE labels FR/NFR/NONE via `IsFunctional` and `IsQuality` one-hot columns; NFR subtypes derived from 12 quality-attribute columns (availability, security, performance, etc.)
- Low NFR coverage across all systems is partly a reflection of the evaluation task difficulty: NFRs are less specific and more abstract, making semantic matching harder

---

## 9. Limitations

- **15 projects only** — a larger sample is needed to draw statistically robust conclusions; standard deviations are high (±0.09–0.12 on F1)
- **No revision loops triggered** — the critic's threshold may be too lenient; tighter criteria could surface the multi-agent pipeline's repair capabilities
- **Use-case descriptions are synthetic** — the ground-truth use cases were generated by Claude from the existing requirements, not written by human stakeholders; this may bias all systems in similar ways
- **Semantic threshold sensitivity** — results at threshold = 0.60; a lower threshold (e.g. 0.50) would inflate all scores; relative rankings may shift at different thresholds
- **SME persona quality** — the SME node's domain/persona is determined by the Planner, which may choose suboptimal personas for some project types
