# RE Elicitation Results — Multi-Agent Software Development Assistant

**Dataset:** NICE PROMISE-relabeled (15 projects, 622 ground-truth requirements)  
**Model:** `claude-sonnet-4-6`, `temperature=0`  
**Evaluation:** Semantic cosine similarity via `all-MiniLM-L6-v2`, threshold = 0.60  
**Date:** 2026-04-16  
**Architecture:** V2-SME redesigned — SME acts as domain advisor (advisory context only), not requirement generator

---

## 1. Summary Table

| System | Coverage (Recall) | Precision | Semantic F1 | FR Coverage | NFR Coverage | Avg Reqs/Project | Avg LLM Calls | Avg Tokens/Task | Total Tokens |
|---|---|---|---|---|---|---|---|---|---|
| Single-Agent | **0.497 ± 0.099** | **0.384 ± 0.122** | **0.420 ± 0.100** | **0.647** | **0.302** | 50.0 | 1.0 | 4,839 | 72,590 |
| Multi-Agent V1 | 0.424 ± 0.105 | 0.308 ± 0.103 | 0.348 ± 0.089 | 0.573 | 0.230 | 50.0 | 3.0 | 9,098 | 136,474 |
| Multi-Agent V2 (SME) | 0.327 ± 0.075 | 0.209 ± 0.072 | 0.246 ± 0.059 | 0.465 | 0.176 | 50.0 | 4.1 | 14,455 | 216,830 |

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
| Single-Agent | **0.420** | — |
| Multi-Agent V1 | 0.348 | −0.072 (−17%) |
| Multi-Agent V2 (SME) | 0.246 | −0.174 (−41%) |

Single-Agent achieves the best Semantic F1. Both multi-agent systems underperform the single-shot baseline on all three metrics.

### FR vs NFR Coverage

All systems cover Functional Requirements substantially better than Non-Functional Requirements:

| System | FR Coverage | NFR Coverage | Gap |
|---|---|---|---|
| Single-Agent | 0.647 | 0.302 | 0.345 |
| Multi-Agent V1 | 0.573 | 0.230 | 0.343 |
| Multi-Agent V2 (SME) | 0.465 | 0.176 | 0.289 |

Despite the SME advisory being designed to surface domain-specific NFR constraints and patterns, V2-SME has the lowest NFR coverage. The advisory context appears to cause the extractor to over-focus on elaborating specific NFR areas while missing others, rather than broadening coverage.

---

## 4. Orchestration Cost

### LLM Calls per Project

| System | Avg Calls | Multiplier vs Single-Agent |
|---|---|---|
| Single-Agent | 1.0 | 1× |
| Multi-Agent V1 | 3.0 | 3× |
| Multi-Agent V2 (SME) | 4.1 | 4.1× |

Multi-Agent V1 uses exactly 3 calls per project (Planner + Extractor + Critic) — the critic approved all 15 projects on first pass. V2 adds a 4th call for the SME advisory node; occasional 6-call projects (2nd critique cycle) push the average above 4.

### Tokens per Task

| System | Avg Tokens | Multiplier vs Single-Agent | Total Tokens |
|---|---|---|---|
| Single-Agent | 4,839 | 1× | 72,590 |
| Multi-Agent V1 | 9,098 | 1.9× | 136,474 |
| Multi-Agent V2 (SME) | 14,455 | 3.0× | 216,830 |

V2 uses 3× more tokens than Single-Agent per project due to the SME advisory call and the SME context block injected into the extractor prompt.

---

## 5. Quality vs Cost Trade-off

Single-Agent produces the best Semantic F1 at the lowest cost. The multi-agent systems pay 3–4× in LLM calls and 1.9–3× in tokens for *lower* quality on this task.

| System | Semantic F1 | Total Tokens | F1 per 1K Tokens |
|---|---|---|---|
| Single-Agent | 0.420 | 72,590 | 0.0058 |
| Multi-Agent V1 | 0.348 | 136,474 | 0.0026 |
| Multi-Agent V2 (SME) | 0.246 | 216,830 | 0.0011 |

Single-Agent is **5.3× more token-efficient** than V2 on this task.

---

## 6. Key Finding: Single-Agent Wins on RE Elicitation

RE Elicitation shows a clear ranking: **simpler is better**.

**Why the multi-agent systems underperform:**

1. **Planner constrains the extractor.** The Planner node produces a strategy and a fixed list of key quality attributes. This narrows the Extractor's focus — useful for correctness on well-specified tasks, but harmful for open-ended elicitation where breadth matters.

2. **Critic approves too readily.** The Critic approved all 15 projects on first pass — no revision loops ran at all. This means the multi-agent overhead of planner + critic adds cost with no quality benefit when the baseline output is already "good enough" by the critic's assessment.

3. **SME advisory introduces topic drift.** In the redesigned V2, the SME provides advisory context (domain constraints, requirement patterns, risks) that the extractor incorporates. While the intent is to improve domain precision, the advisory context pulls the extractor toward specific regulatory/compliance concerns while reducing its breadth — lowering both coverage and precision compared to unconstrained generation.

4. **Single-agent generates more freely.** With no planner constraining it and no advisory context to narrow focus, the single-agent prompt elicits a broader, more natural set of requirements that aligns better with the ground truth's diversity.

---

## 7. Cost Summary

| System | Total Tokens | Est. Cost @ claude-sonnet-4-6 |
|---|---|---|
| Single-Agent | 72,590 | ~$0.22 |
| Multi-Agent V1 | 136,474 | ~$0.41 |
| Multi-Agent V2 (SME) | 216,830 | ~$0.65 |
| **Total** | **425,894** | **~$1.28** |

---

## 8. Dataset Notes

- **15 projects** from the NICE PROMISE-relabeled dataset (projects with ≥ 4 requirements)
- **622 total ground-truth requirements** (mix of FR, NFR, and NONE labels)
- **Use-case descriptions** were synthesized by Claude from each project's requirements (offline preprocessing via `prepare_re_elicitation.py`), then used as input to all three systems — ensuring a fair, identical input across systems
- **Ground-truth split:** NICE labels FR/NFR/NONE via `IsFunctional` and `IsQuality` one-hot columns; NFR subtypes derived from 12 quality-attribute columns (availability, security, performance, etc.)
- All systems generate **up to 50 requirements** per project (increased from 20 in earlier runs to allow fuller coverage)
- Low NFR coverage across all systems is partly a reflection of the evaluation task difficulty: NFRs are less specific and more abstract, making semantic matching harder

---

## 9. Limitations

- **15 projects only** — a larger sample is needed to draw statistically robust conclusions; standard deviations are high (±0.06–0.12 on F1)
- **No revision loops triggered** — the critic's threshold may be too lenient; tighter criteria could surface the multi-agent pipeline's repair capabilities
- **Use-case descriptions are synthetic** — the ground-truth use cases were generated by Claude from the existing requirements, not written by human stakeholders; this may bias all systems in similar ways
- **Semantic threshold sensitivity** — results at threshold = 0.60; a lower threshold (e.g. 0.50) would inflate all scores; relative rankings may shift at different thresholds
- **SME advisory quality** — the domain/persona is determined by the Planner, which may choose suboptimal personas for some project types; advisory may narrow rather than broaden coverage
