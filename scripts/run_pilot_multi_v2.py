"""
Run the V2 multi-agent system (with Test Critic) on the codegen pilot.

Usage (from project root):
    python scripts/run_pilot_multi_v2.py

Outputs go to outputs/multi_agent_v2/
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.systems.multi_agent.codegen_graph_v2 import build_codegen_graph_v2, make_initial_state
from src.evaluation.cost_tracker import CostTracker

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = "outputs/multi_agent_v2"
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
    print(f"  Saved {len(records)} records → {path}")


def run_codegen_pilot(pilot_path: str) -> None:
    if not os.path.exists(pilot_path):
        print(f"  SKIP (not found): {pilot_path}")
        return

    records = load_jsonl(pilot_path)
    print(f"\n[CodeGen V2] Running multi-agent+test-critic on {len(records)} problems...")

    graph = build_codegen_graph_v2()
    tracker = CostTracker(system="multi_agent_v2", dataset="codegen")
    solutions = []
    test_results = []

    for rec in records:
        initial_state = make_initial_state(rec)
        result = graph.invoke(initial_state)

        final_code = result.get("final_code", "# no code generated")
        test_result = result.get("test_result", {})
        augmented = result.get("augmented_test_code")
        critique_iters = result.get("test_critique_iteration", 0)

        solutions.append({"task_id": rec["id"], "code": final_code})
        test_results.append(test_result)

        tracker.record(
            llm_calls=result.get("llm_calls", 0),
            total_tokens=result.get("total_tokens", 0),
            task_id=rec["id"],
        )

        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        augmented_note = f"  [test_critic ran {critique_iters}x]" if critique_iters else ""
        print(
            f"  {rec['id']} → {status}"
            f"  [{result.get('llm_calls', 0)} calls]{augmented_note}"
        )
        if augmented and augmented != rec.get("test_code", ""):
            print(f"    └─ test suite augmented by critic")

    out_path = os.path.join(OUTPUT_DIR, f"codegen_solutions_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(solutions, out_path)

    tests_path = os.path.join(OUTPUT_DIR, f"codegen_tests_pilot_{TIMESTAMP}.jsonl")
    write_jsonl(test_results, tests_path)

    cost_path = os.path.join(OUTPUT_DIR, f"codegen_cost_{TIMESTAMP}.json")
    tracker.save(cost_path)

    n_passed = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"\n  pass@1: {n_passed}/{len(test_results)}")
    print(f"  Avg LLM calls: {tracker.summary()['avg_llm_calls']:.2f}")


def main() -> None:
    print("=== Multi-Agent V2 Pilot Run (with Test Critic) ===")
    run_codegen_pilot("data/pilots/codegen_pilot10.jsonl")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
