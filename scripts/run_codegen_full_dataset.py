"""
Run all three systems on the full 164-problem HumanEval+ dataset.

Usage (from project root):
    python scripts/run_codegen_full_dataset.py [--system single|multi|v2|all]

Outputs go to:
    outputs/single_agent/full_*
    outputs/multi_agent/full_*
    outputs/multi_agent_v2/full_*
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.evaluation.cost_tracker import CostTracker
from src.evaluation.codegen_metrics import run_single_test
from src.utils.json_utils import strip_markdown_fences

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
DATA_PATH = "data/processed/humaneval_plus.jsonl"


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


# ── Single-agent ──────────────────────────────────────────────────────────────

def run_single(records: list[dict]) -> None:
    from src.systems.single_agent.codegen_agent import CodeGenAgent

    out_dir = "outputs/single_agent"
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n[single_agent] Running on {len(records)} problems...")

    agent = CodeGenAgent()
    tracker = CostTracker(system="single_agent", dataset="codegen_full")
    solutions, test_results = [], []

    for i, rec in enumerate(records, 1):
        sol, usage = agent.generate(rec)
        solutions.append(sol)
        tracker.record(llm_calls=usage["llm_calls"], total_tokens=usage["total_tokens"], task_id=rec["id"])

        result = run_single_test(
            code=strip_markdown_fences(sol.code),
            test_code=rec.get("test_code", ""),
            task_id=rec["id"],
            attempt=1,
        )
        test_results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{i:3d}/164] {rec['id']} -> {status}")

    write_jsonl(solutions, f"{out_dir}/full_codegen_solutions_{TIMESTAMP}.jsonl")
    write_jsonl([r.model_dump() for r in test_results], f"{out_dir}/full_codegen_tests_{TIMESTAMP}.jsonl")
    tracker.save(f"{out_dir}/full_codegen_cost_{TIMESTAMP}.json")

    n = sum(r.passed for r in test_results)
    print(f"  pass@1: {n}/{len(test_results)}  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}")


# ── Multi-agent V1 ────────────────────────────────────────────────────────────

def run_multi(records: list[dict]) -> None:
    from src.systems.multi_agent.codegen_graph import build_codegen_graph, make_initial_state

    out_dir = "outputs/multi_agent"
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n[multi_agent] Running on {len(records)} problems...")

    graph = build_codegen_graph()
    tracker = CostTracker(system="multi_agent", dataset="codegen_full")
    solutions, test_results = [], []

    for i, rec in enumerate(records, 1):
        result = graph.invoke(make_initial_state(rec))
        final_code = result.get("final_code", "# no code")
        test_result = result.get("test_result", {})

        solutions.append({"task_id": rec["id"], "code": final_code})
        test_results.append(test_result)
        tracker.record(llm_calls=result.get("llm_calls", 0), total_tokens=result.get("total_tokens", 0), task_id=rec["id"])

        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        print(f"  [{i:3d}/164] {rec['id']} -> {status}  [{result.get('llm_calls', 0)} calls]")

    write_jsonl(solutions, f"{out_dir}/full_codegen_solutions_{TIMESTAMP}.jsonl")
    write_jsonl(test_results, f"{out_dir}/full_codegen_tests_{TIMESTAMP}.jsonl")
    tracker.save(f"{out_dir}/full_codegen_cost_{TIMESTAMP}.json")

    n = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"  pass@1: {n}/{len(test_results)}  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}")


# ── Multi-agent V2 (test critic) ──────────────────────────────────────────────

def run_multi_v2(records: list[dict]) -> None:
    from src.systems.multi_agent.codegen_graph_v2 import build_codegen_graph_v2, make_initial_state

    out_dir = "outputs/multi_agent_v2"
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n[multi_agent_v2] Running on {len(records)} problems...")

    graph = build_codegen_graph_v2()
    tracker = CostTracker(system="multi_agent_v2", dataset="codegen_full")
    solutions, test_results = [], []

    for i, rec in enumerate(records, 1):
        result = graph.invoke(make_initial_state(rec))
        final_code = result.get("final_code", "# no code")
        test_result = result.get("test_result", {})
        critique_iters = result.get("test_critique_iteration", 0)

        solutions.append({"task_id": rec["id"], "code": final_code})
        test_results.append(test_result)
        tracker.record(llm_calls=result.get("llm_calls", 0), total_tokens=result.get("total_tokens", 0), task_id=rec["id"])

        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        critic_note = f" [critic×{critique_iters}]" if critique_iters else ""
        print(f"  [{i:3d}/164] {rec['id']} -> {status}  [{result.get('llm_calls', 0)} calls]{critic_note}")

    write_jsonl(solutions, f"{out_dir}/full_codegen_solutions_{TIMESTAMP}.jsonl")
    write_jsonl(test_results, f"{out_dir}/full_codegen_tests_{TIMESTAMP}.jsonl")
    tracker.save(f"{out_dir}/full_codegen_cost_{TIMESTAMP}.json")

    n = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"  pass@1: {n}/{len(test_results)}  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=["single", "multi", "v2", "all"], default="all")
    args = parser.parse_args()

    records = load_jsonl(DATA_PATH)
    print(f"=== Full Run — {len(records)} problems ===")

    if args.system in ("single", "all"):
        run_single(records)
    if args.system in ("multi", "all"):
        run_multi(records)
    if args.system in ("v2", "all"):
        run_multi_v2(records)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
