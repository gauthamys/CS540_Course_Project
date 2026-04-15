"""
RE Combiner node — System 3 only.

Merges draft_requirements (extractor) + sme_requirements (SME node) into
combined_requirements using embedding-based deduplication.

A generated SME requirement is kept only if its cosine similarity to every
existing extractor requirement is below the dedup threshold (default 0.7).
This prevents the SME from restating requirements the extractor already produced.

No LLM call is made — pure Python via sentence-transformers.
If sentence-transformers is not installed, falls back to simple concatenation.
"""
import os
from typing import Optional

DEDUP_THRESHOLD = float(os.getenv("RE_COMBINER_DEDUP_THRESHOLD", "0.7"))


def _cosine_sim(a, b) -> float:
    """Cosine similarity between two numpy vectors."""
    import numpy as np
    dot = float(np.dot(a, b))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return dot / norm if norm > 0 else 0.0


def _deduplicate(
    main_reqs: list[dict],
    sme_reqs: list[dict],
    threshold: float = DEDUP_THRESHOLD,
) -> list[dict]:
    """Return sme_reqs entries that are not near-duplicates of any main_req."""
    if not sme_reqs:
        return []
    if not main_reqs:
        return sme_reqs

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        main_texts = [r.get("text", "") for r in main_reqs]
        sme_texts = [r.get("text", "") for r in sme_reqs]

        main_embs = model.encode(main_texts, normalize_embeddings=True)
        sme_embs = model.encode(sme_texts, normalize_embeddings=True)

        unique_sme = []
        for i, (sme_req, sme_emb) in enumerate(zip(sme_reqs, sme_embs)):
            max_sim = max(_cosine_sim(sme_emb, me) for me in main_embs)
            if max_sim < threshold:
                unique_sme.append(sme_req)
        return unique_sme

    except ImportError:
        # sentence-transformers not available — return all SME reqs (no dedup)
        return sme_reqs


def re_combiner_node(state: dict) -> dict:
    """LangGraph node: merge extractor + SME requirements with deduplication."""
    draft_requirements = state.get("draft_requirements", [])
    sme_requirements = state.get("sme_requirements", [])

    unique_sme = _deduplicate(draft_requirements, sme_requirements)

    # Re-number req_ids across the combined list
    combined = list(draft_requirements)
    offset = len(combined) + 1
    for i, req in enumerate(unique_sme):
        req = dict(req)
        req["req_id"] = f"C{offset + i:03d}"
        combined.append(req)

    return {
        "combined_requirements": combined,
        # llm_calls += 0  (no LLM call)
    }
