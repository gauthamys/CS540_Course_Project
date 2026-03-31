"""
Requirements Engineering evaluation metrics.

Uses sklearn.classification_report as the computation backend.
"""
from sklearn.metrics import classification_report, f1_score


def compute_re_metrics(
    predictions: list[dict],
    ground_truth: list[dict],
    label_key: str = "requirement_type",
) -> dict:
    """
    Compute precision, recall, F1 (macro and per-class) for RE classification.

    Args:
        predictions: list of dicts with keys 'id' and label_key
        ground_truth: list of dicts with keys 'id' and 'label'
        label_key: the key in predictions holding the predicted label
                   (REPrediction uses 'requirement_type')

    Returns:
        dict with 'macro_f1', 'per_class', and the full sklearn report dict
    """
    # Align by id
    gt_by_id = {r["id"]: r for r in ground_truth}
    y_true, y_pred = [], []

    for pred in predictions:
        pid = pred.get("id") or pred.get("task_id")
        gt = gt_by_id.get(pid)
        if gt is None:
            continue
        y_true.append(gt["label"].upper())
        y_pred.append(str(pred.get(label_key, "NONE")).upper())

    if not y_true:
        return {"macro_f1": 0.0, "per_class": {}, "sklearn_report": {}}

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    return {
        "macro_f1": macro_f1,
        "per_class": {
            label: {
                "precision": v["precision"],
                "recall": v["recall"],
                "f1": v["f1-score"],
                "support": v["support"],
            }
            for label, v in report.items()
            if isinstance(v, dict)
        },
        "sklearn_report": report,
        "n_samples": len(y_true),
    }


def compute_secreq_metrics(predictions: list[dict], ground_truth: list[dict]) -> dict:
    """
    Binary classification metrics for the SecReq dataset.
    Uses the 'label' field (security / non-security) from ground truth
    and 'requirement_type' from predictions — mapping FR/NFR→security, NONE→non-security
    as a secondary mapping, OR using is_security_relevant directly.
    """
    gt_by_id = {r["id"]: r for r in ground_truth}
    y_true, y_pred = [], []

    for pred in predictions:
        pid = pred.get("id") or pred.get("task_id")
        gt = gt_by_id.get(pid)
        if gt is None:
            continue
        y_true.append(gt["label"])

        # Prefer is_security_relevant if set
        isr = pred.get("is_security_relevant")
        if isr is True:
            y_pred.append("security")
        elif isr is False:
            y_pred.append("non-security")
        else:
            # Fall back: NFR/security subtype → security, else non-security
            rt = str(pred.get("requirement_type", "NONE")).upper()
            sub = str(pred.get("nfr_subtype") or "").lower()
            if rt == "NFR" and sub == "security":
                y_pred.append("security")
            else:
                y_pred.append("non-security")

    if not y_true:
        return {"macro_f1": 0.0, "per_class": {}, "sklearn_report": {}}

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    return {
        "macro_f1": macro_f1,
        "per_class": {
            label: {
                "precision": v["precision"],
                "recall": v["recall"],
                "f1": v["f1-score"],
                "support": v["support"],
            }
            for label, v in report.items()
            if isinstance(v, dict)
        },
        "sklearn_report": report,
        "n_samples": len(y_true),
    }
