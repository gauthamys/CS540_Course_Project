"""
Evaluate RE Elicitation results saved by run_re_elicitation.py.

Usage (from project root):
    python scripts/evaluate_re_elicitation.py [--results GLOB_PATTERN] [--threshold FLOAT]

Example:
    python scripts/evaluate_re_elicitation.py
    python scripts/evaluate_re_elicitation.py --results "outputs/re_elicitation/*/results_*.jsonl"
    python scripts/evaluate_re_elicitation.py --threshold 0.5

Prints a summary table and saves:
    outputs/re_elicitation/evaluation_<TIMESTAMP>.json
"""
import os
import sys
import json
import glob
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.evaluation.re_elicitation_metrics import (
    compute_metrics,
    aggregate_metrics,
    SIM_THRESHOLD,
)

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
DEFAULT_RESULTS_GLOB = "outputs/re_elicitation/*/results_*.jsonl"
OUTPUT_DIR = "outputs/re_elicitation"


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def latest_results_per_system() -> dict[str, str]:
    """Find the most recent results file for each system."""
    found = {}
    for system in ("single_agent", "multi_agent_v1", "multi_agent_v2_sme"):
        files = sorted(glob.glob(f"outputs/re_elicitation/{system}/results_*.jsonl"))
        if files:
            found[system] = files[-1]
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=str, default=None,
                        help="Glob pattern for results JSONL files. Defaults to latest per system.")
    parser.add_argument("--threshold", type=float, default=SIM_THRESHOLD,
                        help=f"Cosine similarity threshold (default {SIM_THRESHOLD})")
    args = parser.parse_args()

    print("=== RE Elicitation Evaluation ===")
    print(f"  Similarity threshold: {args.threshold}")

    # Collect result files
    if args.results:
        result_files = sorted(glob.glob(args.results))
    else:
        latest = latest_results_per_system()
        result_files = list(latest.values())

    if not result_files:
        print("No result files found. Run scripts/run_re_elicitation.py first.")
        sys.exit(1)

    # Group records by system
    by_system: dict[str, list[dict]] = {}
    for fpath in result_files:
        records = load_jsonl(fpath)
        for r in records:
            system = r.get("system", "unknown")
            by_system.setdefault(system, []).append(r)
        print(f"  Loaded {len(records)} results from {fpath}")

    # Evaluate each system
    all_results = {}
    for system, records in sorted(by_system.items()):
        print(f"\n  Evaluating {system} ({len(records)} projects)...")
        per_project = []
        for rec in records:
            m = compute_metrics(
                project_id=rec["project_id"],
                system=system,
                generated=rec.get("generated_requirements", []),
                ground_truth=rec.get("ground_truth_requirements", []),
                threshold=args.threshold,
            )
            per_project.append(m)

        summary = aggregate_metrics(per_project)
        all_results[system] = {
            "summary": summary,
            "per_project": [m.to_dict() for m in per_project],
        }

        print(f"    coverage (recall): {summary.get('mean_coverage', 0):.3f} "
              f"± {summary.get('std_coverage', 0):.3f}")
        print(f"    precision:         {summary.get('mean_precision', 0):.3f} "
              f"± {summary.get('std_precision', 0):.3f}")
        print(f"    semantic F1:       {summary.get('mean_semantic_f1', 0):.3f} "
              f"± {summary.get('std_semantic_f1', 0):.3f}")
        print(f"    FR coverage:       {summary.get('mean_fr_coverage', 0):.3f}")
        print(f"    NFR coverage:      {summary.get('mean_nfr_coverage', 0):.3f}")

    # Summary table
    print("\n" + "=" * 70)
    print(f"{'System':<28} {'Coverage':>10} {'Precision':>10} {'F1':>10}")
    print("-" * 70)
    for system, res in sorted(all_results.items()):
        s = res["summary"]
        print(f"{system:<28} {s.get('mean_coverage', 0):>10.3f} "
              f"{s.get('mean_precision', 0):>10.3f} "
              f"{s.get('mean_semantic_f1', 0):>10.3f}")
    print("=" * 70)

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = f"{OUTPUT_DIR}/evaluation_{TIMESTAMP}.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Full results saved → {out_path}")


if __name__ == "__main__":
    main()
