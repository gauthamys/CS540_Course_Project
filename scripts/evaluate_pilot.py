"""
Load pilot outputs from both systems and print a comparison table.

Usage:
    python scripts/evaluate_pilot.py \\
        --nice-single   outputs/single_agent/nice_pilot_TIMESTAMP.jsonl \\
        --nice-multi    outputs/multi_agent/nice_pilot_TIMESTAMP.jsonl \\
        --nice-gt       data/pilots/nice_pilot10.jsonl \\
        --secreq-single outputs/single_agent/secreq_pilot_TIMESTAMP.jsonl \\
        --secreq-multi  outputs/multi_agent/secreq_pilot_TIMESTAMP.jsonl \\
        --secreq-gt     data/pilots/secreq_pilot10.jsonl \\
        --cg-single-tests  outputs/single_agent/codegen_tests_pilot_TIMESTAMP.jsonl \\
        --cg-multi-tests   outputs/multi_agent/codegen_tests_pilot_TIMESTAMP.jsonl

Or auto-discover latest output files:
    python scripts/evaluate_pilot.py --auto
"""
import os
import sys
import json
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.re_metrics import compute_re_metrics, compute_secreq_metrics
from src.evaluation.codegen_metrics import compute_codegen_metrics
from src.schemas.codegen_schema import TestRunResult


def load_jsonl(path: str) -> list[dict]:
    if not path or not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def latest_file(pattern: str) -> str:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def print_table(rows: list[dict]) -> None:
    """Print a simple ASCII comparison table."""
    cols = ["dataset", "system", "macro_f1", "pass@1", "avg_llm_calls", "avg_tokens"]
    col_w = {c: max(len(c), max((len(str(r.get(c, ""))) for r in rows), default=0)) + 2 for c in cols}

    header = " | ".join(c.ljust(col_w[c]) for c in cols)
    sep = "-+-".join("-" * col_w[c] for c in cols)
    print("\n" + header)
    print(sep)
    for row in rows:
        print(" | ".join(str(row.get(c, "N/A")).ljust(col_w[c]) for c in cols))
    print()


def evaluate(args) -> None:
    rows = []

    # ── Load cost summaries ───────────────────────────────────────────────────
    def get_avg_calls(cost_pattern: str) -> tuple[float, float]:
        path = latest_file(cost_pattern) if args.auto else ""
        if not path:
            return 0.0, 0.0
        data = json.load(open(path))
        s = data.get("summary", {})
        return s.get("avg_llm_calls", 0.0), s.get("avg_tokens", 0.0)

    # ── NICE ──────────────────────────────────────────────────────────────────
    nice_gt = load_jsonl(args.nice_gt if not args.auto else "data/pilots/nice_pilot10.jsonl")

    for system, pred_path, cost_pat in [
        ("single_agent", args.nice_single, "outputs/single_agent/nice_cost_*.json"),
        ("multi_agent",  args.nice_multi,  "outputs/multi_agent/nice_cost_*.json"),
    ]:
        if args.auto:
            pred_path = latest_file(f"outputs/{system}/nice_pilot_*.jsonl")
        preds = load_jsonl(pred_path)
        if preds and nice_gt:
            metrics = compute_re_metrics(preds, nice_gt)
            avg_calls, avg_tokens = get_avg_calls(cost_pat)
            rows.append({
                "dataset": "NICE",
                "system": system,
                "macro_f1": f"{metrics['macro_f1']:.3f}",
                "pass@1": "N/A",
                "avg_llm_calls": f"{avg_calls:.1f}",
                "avg_tokens": f"{avg_tokens:.0f}",
            })

    # ── SecReq ────────────────────────────────────────────────────────────────
    secreq_gt = load_jsonl(args.secreq_gt if not args.auto else "data/pilots/secreq_pilot10.jsonl")

    for system, pred_path, cost_pat in [
        ("single_agent", args.secreq_single, "outputs/single_agent/secreq_cost_*.json"),
        ("multi_agent",  args.secreq_multi,  "outputs/multi_agent/secreq_cost_*.json"),
    ]:
        if args.auto:
            pred_path = latest_file(f"outputs/{system}/secreq_pilot_*.jsonl")
        preds = load_jsonl(pred_path)
        if preds and secreq_gt:
            metrics = compute_secreq_metrics(preds, secreq_gt)
            avg_calls, avg_tokens = get_avg_calls(cost_pat)
            rows.append({
                "dataset": "SecReq",
                "system": system,
                "macro_f1": f"{metrics['macro_f1']:.3f}",
                "pass@1": "N/A",
                "avg_llm_calls": f"{avg_calls:.1f}",
                "avg_tokens": f"{avg_tokens:.0f}",
            })

    # ── CodeGen ───────────────────────────────────────────────────────────────
    for system, tests_path, cost_pat in [
        ("single_agent", args.cg_single_tests, "outputs/single_agent/codegen_cost_*.json"),
        ("multi_agent",  args.cg_multi_tests,  "outputs/multi_agent/codegen_cost_*.json"),
    ]:
        if args.auto:
            tests_path = latest_file(f"outputs/{system}/codegen_tests_pilot_*.jsonl")
        tests = load_jsonl(tests_path)
        if tests:
            metrics = compute_codegen_metrics(tests)
            avg_calls, avg_tokens = get_avg_calls(cost_pat)
            rows.append({
                "dataset": "CodeGen",
                "system": system,
                "macro_f1": "N/A",
                "pass@1": f"{metrics['pass_at_1']:.3f}",
                "avg_llm_calls": f"{avg_calls:.1f}",
                "avg_tokens": f"{avg_tokens:.0f}",
            })

    if rows:
        print_table(rows)
    else:
        print("No output files found. Run run_pilot_single.py and run_pilot_multi.py first.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare single-agent vs multi-agent pilot results")
    parser.add_argument("--auto", action="store_true", help="Auto-discover latest output files")
    parser.add_argument("--nice-single", default="")
    parser.add_argument("--nice-multi", default="")
    parser.add_argument("--nice-gt", default="data/pilots/nice_pilot10.jsonl")
    parser.add_argument("--secreq-single", default="")
    parser.add_argument("--secreq-multi", default="")
    parser.add_argument("--secreq-gt", default="data/pilots/secreq_pilot10.jsonl")
    parser.add_argument("--cg-single-tests", default="")
    parser.add_argument("--cg-multi-tests", default="")
    args = parser.parse_args()

    evaluate(args)


if __name__ == "__main__":
    main()
