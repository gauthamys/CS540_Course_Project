"""
Run the single-agent baseline on all three pilot files.

Usage (from project root):
    python scripts/run_codegen_single_agent.py

Outputs go to outputs/single_agent/{dataset}_pilot_{timestamp}.jsonl
Cost summaries go to outputs/single_agent/{dataset}_cost_{timestamp}.json
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.systems.single_agent.re_agent import REAgent
from src.systems.single_agent.codegen_agent import CodeGenAgent
from src.evaluation.codegen_metrics import run_single_test
from src.evaluation.cost_tracker import CostTracker

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = "outputs/single_agent"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list, path: str) -> None:
    with open(path, "w") as f:
        for r in records:
            obj = r.model_dump() if hasattr(r, "model_dump") else r
            f.write(json.dumps(obj) + "\n")
    print(f"  Saved {len(records)} records -> {path}")


def run_re_pilot(pilot_path: str, dataset_name: str) -> None:
    if not os.path.exists(pilot_path):
        print(f"  SKIP (not found): {pilot_path}")
        return

    records = load_jsonl(pilot_path)
    print(f"\n[RE / {dataset_name}] Running single-agent on {len(records)} records...")

    agent = REAgent()
    tracker = CostTracker(system="single_agent", dataset=dataset_name)
    predictions = []

    for rec in records:
        pred, usage = agent.classify(rec)
        predictions.append(pred)
        tracker.record(
            llm_calls=usage["llm_calls"],
            total_tokens=usage["total_tokens"],
            task_id=rec["id"],
        )
        print(f"  {rec['id']} -> {pred.requirement_type} ({pred.nfr_subtype or '-'})")

    out_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(predictions, out_path)

    cost_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_cost_{TIMESTAMP}.json")
    tracker.save(cost_path)
    print(f"  Avg LLM calls: {tracker.summary()['avg_llm_calls']:.2f}")


def run_codegen_pilot(pilot_path: str) -> None:
    if not os.path.exists(pilot_path):
        print(f"  SKIP (not found): {pilot_path}")
        return

    records = load_jsonl(pilot_path)
    print(f"\n[CodeGen] Running single-agent on {len(records)} problems...")

    agent = CodeGenAgent()
    tracker = CostTracker(system="single_agent", dataset="codegen")
    solutions = []
    test_results = []

    for rec in records:
        sol, usage = agent.generate(rec)
        solutions.append(sol)
        tracker.record(
            llm_calls=usage["llm_calls"],
            total_tokens=usage["total_tokens"],
            task_id=rec["id"],
        )

        # Run tests
        test_result = run_single_test(
            code=sol.code,
            test_code=rec.get("test_code", ""),
            task_id=rec["id"],
            attempt=1,
        )
        test_results.append(test_result)
        status = "PASS" if test_result.passed else "FAIL"
        print(f"  {rec['id']} -> {status}")

    out_path = os.path.join(OUTPUT_DIR, f"codegen_solutions_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(solutions, out_path)

    tests_path = os.path.join(OUTPUT_DIR, f"codegen_tests_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(test_results, tests_path)

    cost_path = os.path.join(OUTPUT_DIR, f"codegen_cost_{TIMESTAMP}.json")
    tracker.save(cost_path)

    n_passed = sum(r.passed for r in test_results)
    print(f"  pass@1: {n_passed}/{len(test_results)}")


def main() -> None:
    print("=== Single-Agent Pilot Run ===")
    run_re_pilot("data/pilots/nice_pilot10.jsonl", "nice")
    run_re_pilot("data/pilots/secreq_pilot10.jsonl", "secreq")
    run_codegen_pilot("data/pilots/codegen_pilot10.jsonl")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
