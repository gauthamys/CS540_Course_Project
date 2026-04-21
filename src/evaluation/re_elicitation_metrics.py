"""
Evaluation metrics for the RE Elicitation task.

Compares generated requirements against ground-truth requirements using
semantic similarity (sentence-transformers, all-MiniLM-L6-v2).

Metrics:
  - coverage (recall): fraction of GT reqs with best cosine sim >= threshold to any generated req
  - precision: fraction of generated reqs with best cosine sim >= threshold to any GT req
  - semantic_f1: harmonic mean of coverage and precision
  - fr_coverage, nfr_coverage: type-specific coverage

Requires: pip install sentence-transformers
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Optional

SIM_THRESHOLD = float(os.getenv("RE_SIM_THRESHOLD", "0.6"))


@dataclass
class REElicitationMetrics:
    project_id: str
    system: str
    coverage: float           # recall over GT
    precision: float          # precision over generated
    semantic_f1: float
    fr_coverage: float        # FR-specific recall
    nfr_coverage: float       # NFR-specific recall
    n_generated: int
    n_ground_truth: int
    threshold: float = SIM_THRESHOLD

    def to_dict(self) -> dict:
        return asdict(self)


_MODEL_CACHE = None


def _load_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL_CACHE = SentenceTransformer("all-MiniLM-L6-v2")
        return _MODEL_CACHE
    except ImportError:
        raise ImportError(
            "sentence-transformers is required for RE evaluation. "
            "Run: pip install sentence-transformers"
        )


def _cosine_sim_matrix(embs_a, embs_b):
    """Return n_a × n_b cosine similarity matrix (both inputs already L2-normalised)."""
    import numpy as np
    return (embs_a @ embs_b.T).clip(-1, 1)


def compute_metrics(
    project_id: str,
    system: str,
    generated: list[dict],
    ground_truth: list[dict],
    threshold: float = SIM_THRESHOLD,
) -> REElicitationMetrics:
    """
    Compute semantic coverage, precision, and F1 for one project.

    Args:
        project_id: identifier for the project
        system: system name ("single_agent", "multi_agent_v1", "multi_agent_v2_sme")
        generated: list of GeneratedRequirement dicts
        ground_truth: list of ground-truth record dicts (must have "text" and "label")
        threshold: cosine similarity threshold to count a match

    Returns:
        REElicitationMetrics
    """
    if not generated or not ground_truth:
        return REElicitationMetrics(
            project_id=project_id,
            system=system,
            coverage=0.0,
            precision=0.0,
            semantic_f1=0.0,
            fr_coverage=0.0,
            nfr_coverage=0.0,
            type_aware_coverage=0.0,
            type_aware_precision=0.0,
            type_aware_f1=0.0,
            n_generated=len(generated),
            n_ground_truth=len(ground_truth),
            threshold=threshold,
        )

    import numpy as np

    model = _load_model()

    gen_texts = [r.get("text", "") for r in generated]
    gt_texts = [r.get("text", "") for r in ground_truth]

    gen_embs = model.encode(gen_texts, normalize_embeddings=True)
    gt_embs = model.encode(gt_texts, normalize_embeddings=True)

    # sim_matrix[i, j] = cosine sim between gt[i] and gen[j]
    sim_matrix = _cosine_sim_matrix(gt_embs, gen_embs)

    # Coverage (recall): for each GT req, is there a generated req with sim >= threshold?
    gt_matched = (sim_matrix.max(axis=1) >= threshold)
    coverage = float(gt_matched.mean())

    # Precision: for each generated req, is there a GT req with sim >= threshold?
    gen_matched = (sim_matrix.max(axis=0) >= threshold)
    precision = float(gen_matched.mean())

    # Semantic F1
    if coverage + precision > 0:
        semantic_f1 = 2 * coverage * precision / (coverage + precision)
    else:
        semantic_f1 = 0.0

    # Type-specific coverage
    fr_indices = [i for i, r in enumerate(ground_truth) if r.get("label", "").upper() == "FR"]
    nfr_indices = [i for i, r in enumerate(ground_truth) if r.get("label", "").upper() == "NFR"]

    fr_coverage = float(gt_matched[fr_indices].mean()) if fr_indices else 0.0
    nfr_coverage = float(gt_matched[nfr_indices].mean()) if nfr_indices else 0.0

    return REElicitationMetrics(
        project_id=project_id,
        system=system,
        coverage=round(coverage, 4),
        precision=round(precision, 4),
        semantic_f1=round(semantic_f1, 4),
        fr_coverage=round(fr_coverage, 4),
        nfr_coverage=round(nfr_coverage, 4),
        n_generated=len(generated),
        n_ground_truth=len(ground_truth),
        threshold=threshold,
    )


def aggregate_metrics(metrics_list: list[REElicitationMetrics]) -> dict:
    """
    Compute macro-average across all projects.

    Returns a summary dict with mean and std for each metric.
    """
    if not metrics_list:
        return {}

    import numpy as np

    fields = ["coverage", "precision", "semantic_f1", "fr_coverage", "nfr_coverage"]
    summary = {"n_projects": len(metrics_list)}

    for f in fields:
        vals = [getattr(m, f) for m in metrics_list]
        summary[f"mean_{f}"] = round(float(np.mean(vals)), 4)
        summary[f"std_{f}"] = round(float(np.std(vals)), 4)

    summary["total_generated"] = sum(m.n_generated for m in metrics_list)
    summary["total_ground_truth"] = sum(m.n_ground_truth for m in metrics_list)

    return summary
