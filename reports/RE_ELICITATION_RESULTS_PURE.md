# RE Elicitation Results — PURE Dataset

**Dataset:** PURE (Pure Requirements) — 15 XML-format specification documents, 1,624 ground-truth requirements  
**Model:** `claude-sonnet-4-6`, `temperature=0`  
**Evaluation:** Semantic cosine similarity via `all-MiniLM-L6-v2`, threshold = 0.60  
**Date:** 2026-04-16  
**Architecture:** V2-SME redesigned — SME acts as domain advisor (advisory context only), not requirement generator

---

## 1. Summary Table

| System | Coverage (Recall) | Precision | Semantic F1 | FR Coverage | NFR Coverage | Avg Reqs/Project | Avg LLM Calls | Avg Tokens/Task | Total Tokens |
|---|---|---|---|---|---|---|---|---|---|
| Single-Agent | **0.359 ± 0.174** | 0.367 ± 0.197 | **0.338 ± 0.148** | **0.352** | 0.186 | 50.0 | 1.0 | 5,044 | 75,658 |
| Multi-Agent V1 | 0.329 ± 0.134 | **0.375 ± 0.200** | 0.325 ± 0.128 | 0.317 | **0.210** | 50.0 | 3.0 | 9,622 | 144,331 |
| Multi-Agent V2 (SME) | 0.260 ± 0.163 | 0.300 ± 0.213 | 0.258 ± 0.158 | 0.254 | 0.085 | 50.0 | 4.0 | 15,475 | 232,122 |

Ground truth: 1,624 requirements across 15 projects.

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
| Single-Agent | **0.338** | — |
| Multi-Agent V1 | 0.325 | −0.013 (−4%) |
| Multi-Agent V2 (SME) | 0.258 | −0.080 (−24%) |

Single-Agent achieves the highest F1, but the gap vs V1 is small (−4%) — unlike NICE where V1 trailed by 17%. On PURE, V1 achieves **higher precision** than Single-Agent (0.375 vs 0.367), indicating its structured planning produces more targeted requirements for formal specification documents.

### FR vs NFR Coverage

| System | FR Coverage | NFR Coverage | Gap |
|---|---|---|---|
| Multi-Agent V1 | 0.317 | **0.210** | 0.107 |
| Single-Agent | 0.352 | 0.186 | 0.166 |
| Multi-Agent V2 (SME) | 0.254 | 0.085 | 0.169 |

NFR coverage is low across all systems. PURE documents are primarily formal functional specifications (railway, public health, security protocols) with few explicit NFRs — making NFR matching inherently difficult. Notably, V1 achieves the **best NFR coverage** (0.210), suggesting that a structured elicitation plan naturally prompts the model to surface quality attributes even when the input spec does not mention them.

---

## 4. Orchestration Cost

### LLM Calls per Project

| System | Avg Calls | Multiplier vs Single-Agent |
|---|---|---|
| Single-Agent | 1.0 | 1× |
| Multi-Agent V1 | 3.0 | 3× |
| Multi-Agent V2 (SME) | 4.0 | 4× |

All critics approved on first pass across all 15 projects — no revision loops triggered.

### Tokens per Task

| System | Avg Tokens | Multiplier vs Single-Agent | Total Tokens |
|---|---|---|---|
| Single-Agent | 5,044 | 1× | 75,658 |
| Multi-Agent V1 | 9,622 | 1.9× | 144,331 |
| Multi-Agent V2 (SME) | 15,475 | 3.1× | 232,122 |

---

## 5. Quality vs Cost Trade-off

| System | Semantic F1 | Total Tokens | F1 per 1K Tokens |
|---|---|---|---|
| Single-Agent | 0.338 | 75,658 | 0.0045 |
| Multi-Agent V1 | 0.325 | 144,331 | 0.0023 |
| Multi-Agent V2 (SME) | 0.258 | 232,122 | 0.0011 |

Single-Agent remains the most token-efficient. V1 closes the quality gap significantly on PURE (F1 within 0.013) but at 1.9× the token cost.

---

## 6. Key Findings: PURE vs NICE

| Metric | NICE Winner | PURE Winner | Notes |
|---|---|---|---|
| Semantic F1 | Single-Agent (0.420) | Single-Agent (0.338) | Consistent across datasets |
| F1 gap (Single vs V1) | −0.072 (17%) | −0.013 (4%) | V1 nearly matches single-agent on PURE |
| V1 Precision | 0.308 | **0.375** | V1 more precise on formal specs |
| NFR Coverage best | Single-Agent (0.302) | **V1 (0.210)** | V1 plans surface more NFRs on PURE |
| V2-SME F1 penalty | −0.174 vs single | −0.080 vs single | Advisory hurts less on PURE |

**Why V1 performs relatively better on PURE than NICE:**

1. **Formal spec documents reward planning.** PURE documents are rigorous, domain-specific XML specifications (ERTMS, EIRENE, PHIN). The Planner's strategy identification and key quality attribute selection provide useful framing for structured standards — unlike open-ended NICE project descriptions where planning narrows rather than focuses.

2. **NFR elicitation benefits from explicit prompting.** PURE ground truth includes more latent NFRs (implied by domain constraints) that aren't surfaced without deliberate prompting. The Planner explicitly names quality attributes, nudging the Extractor to cover them.

3. **Precision advantage.** With 1,624 GT requirements across 15 projects (~108/project on average), the PURE documents are dense and specific. V1's structured approach generates more precisely targeted requirements, reducing noise.

---

## 7. Cost Summary

| System | Total Tokens | Est. Cost @ claude-sonnet-4-6 |
|---|---|---|
| Single-Agent | 75,658 | ~$0.23 |
| Multi-Agent V1 | 144,331 | ~$0.43 |
| Multi-Agent V2 (SME) | 232,122 | ~$0.70 |
| **Total** | **452,111** | **~$1.36** |

---

## 8. Dataset Notes

- **15 projects** from the PURE dataset (XML-format SRS documents, filtered to ≥ 5 requirements)
- **1,624 total ground-truth requirements** — ~108 per project on average (much denser than NICE's ~41/project)
- **Use-case descriptions** synthesized by Claude from a capped sample of ≤ 40 requirements per document (evenly spaced for large docs) via `prepare_re_elicitation_pure.py`
- **Two XML schemas** in PURE: Schema A uses explicit `<req>` tags; Schema B uses leaf `<p>` nodes filtered by "shall/must" keywords — both handled by `src/datasets/pure_loader.py`
- FR/NFR labels inferred from XML section titles and requirement text
- Low NFR coverage reflects PURE's nature as functional specification documents; NFR mentions are sparse and implicit

---

## 9. Limitations

- **15 projects only** — standard deviations are high (±0.13–0.20 on all metrics); results not statistically robust
- **Synthetic use-case descriptions** — ground-truth use cases generated from capped requirement samples, not original stakeholder documents
- **No revision loops triggered** — critic threshold may be too lenient
- **FR/NFR label quality** — PURE labels inferred heuristically from XML structure; may not match human-annotated NFR boundaries
- **Semantic threshold sensitivity** — threshold = 0.60; PURE's longer and more formal requirement texts may warrant a different threshold
