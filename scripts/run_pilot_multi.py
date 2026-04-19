"""
Run the multi-agent system on all three pilot files.

Usage (from project root):
    python scripts/run_pilot_multi.py

Outputs go to outputs/multi_agent/{dataset}_pilot_{timestamp}.jsonl
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.systems.multi_agent.re_graph import build_re_graph, make_initial_state as re_init
from src.systems.multi_agent.codegen_graph import build_codegen_graph, make_initial_state as cg_init
from src.evaluation.cost_tracker import CostTracker

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = "outputs/multi_agent"
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
            obj = r if isinstance(r, dict) else r.model_dump()
            f.write(json.dumps(obj) + "\n")
    print(f"  Saved {len(records)} records -> {path}")


def run_re_pilot(pilot_path: str, dataset_name: str) -> None:
    if not os.path.exists(pilot_path):
        print(f"  SKIP (not found): {pilot_path}")
        return

    records = load_jsonl(pilot_path)
    print(f"\n[RE / {dataset_name}] Running multi-agent on {len(records)} records...")

    graph = build_re_graph()
    tracker = CostTracker(system="multi_agent", dataset=dataset_name)
    predictions = []

    for rec in records:
        initial_state = re_init(rec)
        result = graph.invoke(initial_state)
        pred = result.get("final_prediction") or result.get("draft_prediction") or {}
        predictions.append(pred)
        tracker.record(
            llm_calls=result.get("llm_calls", 0),
            total_tokens=result.get("total_tokens", 0),
            task_id=rec["id"],
        )
        rt = pred.get("requirement_type", "?")
        sub = pred.get("nfr_subtype") or "-"
        print(f"  {rec['id']} -> {rt} ({sub})  [{result.get('llm_calls', 0)} calls]")

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
    print(f"\n[CodeGen] Running multi-agent on {len(records)} problems...")

    graph = build_codegen_graph()
    tracker = CostTracker(system="multi_agent", dataset="codegen")
    solutions = []
    test_results = []

    for rec in records:
        initial_state = cg_init(rec)
        result = graph.invoke(initial_state)
        final_code = result.get("final_code", "# no code generated")
        test_result = result.get("test_result", {})

        solutions.append({"task_id": rec["id"], "code": final_code})
        test_results.append(test_result)
        tracker.record(
            llm_calls=result.get("llm_calls", 0),
            total_tokens=result.get("total_tokens", 0),
            task_id=rec["id"],
        )
        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        print(f"  {rec['id']} -> {status}  [{result.get('llm_calls', 0)} calls]")

    out_path = os.path.join(OUTPUT_DIR, f"codegen_solutions_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(solutions, out_path)

    tests_path = os.path.join(OUTPUT_DIR, f"codegen_tests_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(test_results, tests_path)

    cost_path = os.path.join(OUTPUT_DIR, f"codegen_cost_{TIMESTAMP}.json")
    tracker.save(cost_path)

    n_passed = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"  pass@1: {n_passed}/{len(test_results)}")


def main() -> None:
    print("=== Multi-Agent Pilot Run ===")
    run_re_pilot("data/pilots/nice_pilot10.jsonl", "nice")
    run_re_pilot("data/pilots/secreq_pilot10.jsonl", "secreq")
    run_codegen_pilot("data/pilots/codegen_pilot10.jsonl")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
