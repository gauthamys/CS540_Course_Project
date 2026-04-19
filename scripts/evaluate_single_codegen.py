"""
Evaluate and compare single-agent codegen results against multi-agent.

Usage (from project root):
    python scripts/evaluate_single_codegen.py

Reads the latest results from:
    outputs/single_agent_codegen/   (our results)
    outputs/multi_agent/            (teammates' results)

Saves comparison to:
    outputs/single_agent_codegen/comparison_{timestamp}.json
    outputs/single_agent_codegen/comparison_{timestamp}.txt
"""
import os
import sys
import json
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SINGLE_DIR = "outputs/single_agent_codegen"
MULTI_DIR  = "outputs/multi_agent"
TIMESTAMP  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def latest_file(directory: str, pattern: str) -> str | None:
    matches = glob.glob(os.path.join(directory, pattern))
    return max(matches, key=os.path.getmtime) if matches else None


def compute_metrics(test_results: list[dict]) -> dict:
    n = len(test_results)
    if n == 0:
        return {}
    passed = sum(1 for r in test_results if r.get("passed"))
    return {
        "n_problems": n,
        "n_passed": passed,
        "pass_at_1": round(passed / n, 4),
        "pass_at_1_pct": f"{passed/n:.1%}",
    }


def load_cost(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    summary = data.get("summary", data)
    return {
        "avg_llm_calls": round(summary.get("avg_llm_calls", 0), 2),
        "total_llm_calls": summary.get("total_llm_calls", 0),
        "total_tokens": summary.get("total_tokens", 0),
    }


def main() -> None:
    # --- Find latest single-agent full run ---
    single_tests = latest_file(SINGLE_DIR, "codegen_tests_full_*.jsonl")
    single_cost  = latest_file(SINGLE_DIR, "codegen_cost_full_*.json")

    # --- Find latest multi-agent full run ---
    multi_tests = latest_file(MULTI_DIR, "full_codegen_tests_*.jsonl")
    multi_cost  = latest_file(MULTI_DIR, "full_codegen_cost_*.json")

    if not single_tests:
        print("ERROR: No single-agent full run found in outputs/single_agent_codegen/")
        print("       Run: python scripts/run_single_agent_codegen.py --mode full")
        sys.exit(1)

    if not multi_tests:
        print("WARNING: No multi-agent full run found — skipping comparison")

    # --- Load and compute ---
    single_results  = load_jsonl(single_tests)
    single_metrics  = compute_metrics(single_results)
    single_cost_data = load_cost(single_cost) if single_cost else {}

    multi_metrics   = {}
    multi_cost_data = {}
    if multi_tests:
        multi_results   = load_jsonl(multi_tests)
        multi_metrics   = compute_metrics(multi_results)
        if multi_cost:
            multi_cost_data = load_cost(multi_cost)

    # --- Build comparison dict ---
    comparison = {
        "generated_at": TIMESTAMP,
        "dataset": "HumanEval+",
        "single_agent": {
            "source_file": single_tests,
            "metrics": single_metrics,
            "cost": single_cost_data,
        },
        "multi_agent": {
            "source_file": multi_tests,
            "metrics": multi_metrics,
            "cost": multi_cost_data,
        },
    }

    if multi_metrics:
        diff = single_metrics["pass_at_1"] - multi_metrics["pass_at_1"]
        comparison["delta_pass_at_1"] = round(diff, 4)
        comparison["delta_avg_llm_calls"] = round(
            single_cost_data.get("avg_llm_calls", 0) - multi_cost_data.get("avg_llm_calls", 0), 2
        )

    # --- Save JSON ---
    json_path = os.path.join(SINGLE_DIR, f"comparison_{TIMESTAMP}.json")
    with open(json_path, "w") as f:
        json.dump(comparison, f, indent=2)

    # --- Save human-readable text ---
    txt_path = os.path.join(SINGLE_DIR, f"comparison_{TIMESTAMP}.txt")
    lines = [
        "=" * 60,
        "  Single-Agent vs Multi-Agent — HumanEval+ Comparison",
        "=" * 60,
        "",
        f"  {'Metric':<25} {'Single-Agent':>15} {'Multi-Agent':>15}",
        f"  {'-'*55}",
        f"  {'pass@1':<25} {single_metrics.get('pass_at_1_pct','N/A'):>15} {multi_metrics.get('pass_at_1_pct','N/A'):>15}",
        f"  {'problems passed':<25} {single_metrics.get('n_passed','N/A'):>15} {multi_metrics.get('n_passed','N/A'):>15}",
        f"  {'total problems':<25} {single_metrics.get('n_problems','N/A'):>15} {multi_metrics.get('n_problems','N/A'):>15}",
        f"  {'avg LLM calls':<25} {single_cost_data.get('avg_llm_calls','N/A'):>15} {multi_cost_data.get('avg_llm_calls','N/A'):>15}",
        f"  {'total LLM calls':<25} {single_cost_data.get('total_llm_calls','N/A'):>15} {multi_cost_data.get('total_llm_calls','N/A'):>15}",
        f"  {'total tokens':<25} {single_cost_data.get('total_tokens','N/A'):>15} {multi_cost_data.get('total_tokens','N/A'):>15}",
        "",
    ]

    if "delta_pass_at_1" in comparison:
        delta = comparison["delta_pass_at_1"]
        sign = "+" if delta >= 0 else ""
        lines += [
            f"  pass@1 delta (single - multi) : {sign}{delta:.1%}",
            f"  LLM calls delta               : {sign}{comparison['delta_avg_llm_calls']:.2f} avg calls",
            "",
        ]

    lines.append("=" * 60)

    report = "\n".join(lines)
    with open(txt_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\n  Saved -> {json_path}")
    print(f"  Saved -> {txt_path}")


if __name__ == "__main__":
    main()
