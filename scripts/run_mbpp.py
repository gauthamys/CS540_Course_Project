"""
Run all three code generation systems on MBPP+.

Usage (from project root):
    python scripts/run_mbpp.py [--system single|multi|v2|all] [--pilot] [--max_problems N]

Outputs go to:
    outputs/single_agent/mbpp_solutions_<TIMESTAMP>.jsonl
    outputs/multi_agent/mbpp_solutions_<TIMESTAMP>.jsonl
    outputs/multi_agent_v2/mbpp_solutions_<TIMESTAMP>.jsonl

Each output line:
  {task_id, code}

Test results go to the corresponding mbpp_tests_<TIMESTAMP>.jsonl files.
"""
import os
import sys
import json
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.evaluation.codegen_metrics import run_single_test, compute_codegen_metrics
from src.evaluation.cost_tracker import CostTracker
from src.utils.json_utils import strip_markdown_fences

TIMESTAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
DATA_PATH = "data/processed/mbpp_plus.jsonl"
PILOT_N = 10


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            obj = r if isinstance(r, dict) else r.model_dump()
            f.write(json.dumps(obj) + "\n")
    print(f"  Saved {len(records)} records -> {path}")


def append_jsonl(record, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    obj = record if isinstance(record, dict) else record.model_dump()
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def load_completed_ids(tests_path: str) -> set:
    """Return set of task_ids already in an incremental output file."""
    if not os.path.exists(tests_path):
        return set()
    ids = set()
    with open(tests_path) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line).get("task_id", ""))
    return ids


def prepare_mbpp_data() -> list[dict]:
    """Load MBPP+ from cache or download via evalplus, write to data/processed/."""
    if os.path.exists(DATA_PATH):
        return load_jsonl(DATA_PATH)

    print(f"  {DATA_PATH} not found — fetching from evalplus...")
    from src.datasets.evalplus_loader import load_mbpp_plus
    records = load_mbpp_plus()
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"  Cached {len(records)} MBPP+ problems → {DATA_PATH}")
    return records


# ── Single-agent ──────────────────────────────────────────────────────────────

def run_single(records: list[dict]) -> None:
    from src.systems.single_agent.codegen_agent import CodeGenAgent

    out_dir = "outputs/single_agent"
    os.makedirs(out_dir, exist_ok=True)
    n = len(records)
    sols_path = f"{out_dir}/mbpp_solutions_{TIMESTAMP}.jsonl"
    tests_path = f"{out_dir}/mbpp_tests_{TIMESTAMP}.jsonl"
    done = load_completed_ids(tests_path)
    print(f"\n[single_agent] Running on {n} MBPP+ problems ({len(done)} already done)...")

    agent = CodeGenAgent()
    tracker = CostTracker(system="single_agent", dataset="mbpp_plus")
    test_results = []

    for i, rec in enumerate(records, 1):
        if rec["id"] in done:
            print(f"  [{i:3d}/{n}] {rec['id']} -> SKIP")
            continue
        sol, usage = agent.generate(rec)
        tracker.record(llm_calls=usage["llm_calls"], total_tokens=usage["total_tokens"], task_id=rec["id"])

        result = run_single_test(
            code=strip_markdown_fences(sol.code),
            test_code=rec.get("test_code", ""),
            task_id=rec["id"],
            attempt=1,
        )
        test_results.append(result)
        append_jsonl(sol, sols_path)
        append_jsonl(result.model_dump(), tests_path)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{i:3d}/{n}] {rec['id']} -> {status}")

    tracker.save(f"{out_dir}/mbpp_cost_{TIMESTAMP}.json")
    metrics = compute_codegen_metrics(test_results)
    print(f"  pass@1: {metrics['pass_at_1']:.3f}  ({sum(r.passed for r in test_results)}/{len(test_results)})"
          f"  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}"
          f"  avg_tokens: {tracker.summary()['avg_tokens']:.0f}")


# ── Multi-agent V1 ────────────────────────────────────────────────────────────

def run_multi(records: list[dict]) -> None:
    from src.systems.multi_agent.codegen_graph import build_codegen_graph, make_initial_state

    out_dir = "outputs/multi_agent"
    os.makedirs(out_dir, exist_ok=True)
    n = len(records)
    sols_path = f"{out_dir}/mbpp_solutions_{TIMESTAMP}.jsonl"
    tests_path = f"{out_dir}/mbpp_tests_{TIMESTAMP}.jsonl"
    done = load_completed_ids(tests_path)
    print(f"\n[multi_agent_v1] Running on {n} MBPP+ problems ({len(done)} already done)...")

    graph = build_codegen_graph()
    tracker = CostTracker(system="multi_agent", dataset="mbpp_plus")
    test_results = []

    for i, rec in enumerate(records, 1):
        if rec["id"] in done:
            print(f"  [{i:3d}/{n}] {rec['id']} -> SKIP")
            continue
        result = graph.invoke(make_initial_state(rec))
        final_code = result.get("final_code", "# no code")
        test_result = result.get("test_result", {})

        append_jsonl({"task_id": rec["id"], "code": final_code}, sols_path)
        append_jsonl(test_result or {}, tests_path)
        test_results.append(test_result)
        tracker.record(llm_calls=result.get("llm_calls", 0), total_tokens=result.get("total_tokens", 0), task_id=rec["id"])

        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        print(f"  [{i:3d}/{n}] {rec['id']} -> {status}  [{result.get('llm_calls', 0)} calls]")

    tracker.save(f"{out_dir}/mbpp_cost_{TIMESTAMP}.json")
    metrics = compute_codegen_metrics(test_results)
    n_passed = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"  pass@1: {metrics['pass_at_1']:.3f}  ({n_passed}/{len(test_results)})"
          f"  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}"
          f"  avg_tokens: {tracker.summary()['avg_tokens']:.0f}")


# ── Multi-agent V2 (test critic) ──────────────────────────────────────────────

def run_multi_v2(records: list[dict]) -> None:
    from src.systems.multi_agent.codegen_graph_v2 import build_codegen_graph_v2, make_initial_state

    out_dir = "outputs/multi_agent_v2"
    os.makedirs(out_dir, exist_ok=True)
    n = len(records)
    sols_path = f"{out_dir}/mbpp_solutions_{TIMESTAMP}.jsonl"
    tests_path = f"{out_dir}/mbpp_tests_{TIMESTAMP}.jsonl"
    done = load_completed_ids(tests_path)
    print(f"\n[multi_agent_v2] Running on {n} MBPP+ problems ({len(done)} already done)...")

    graph = build_codegen_graph_v2()
    tracker = CostTracker(system="multi_agent_v2", dataset="mbpp_plus")
    test_results = []

    for i, rec in enumerate(records, 1):
        if rec["id"] in done:
            print(f"  [{i:3d}/{n}] {rec['id']} -> SKIP")
            continue
        result = graph.invoke(make_initial_state(rec))
        final_code = result.get("final_code", "# no code")
        test_result = result.get("test_result", {})
        critique_iters = result.get("test_critique_iteration", 0)

        append_jsonl({"task_id": rec["id"], "code": final_code}, sols_path)
        append_jsonl(test_result or {}, tests_path)
        test_results.append(test_result)
        tracker.record(llm_calls=result.get("llm_calls", 0), total_tokens=result.get("total_tokens", 0), task_id=rec["id"])

        status = "PASS" if (test_result or {}).get("passed", False) else "FAIL"
        critic_note = f" [critic×{critique_iters}]" if critique_iters else ""
        print(f"  [{i:3d}/{n}] {rec['id']} -> {status}  [{result.get('llm_calls', 0)} calls]{critic_note}")

    tracker.save(f"{out_dir}/mbpp_cost_{TIMESTAMP}.json")
    metrics = compute_codegen_metrics(test_results)
    n_passed = sum(1 for r in test_results if (r or {}).get("passed", False))
    print(f"  pass@1: {metrics['pass_at_1']:.3f}  ({n_passed}/{len(test_results)})"
          f"  avg_calls: {tracker.summary()['avg_llm_calls']:.2f}"
          f"  avg_tokens: {tracker.summary()['avg_tokens']:.0f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=["single", "multi", "v2", "all"], default="all")
    parser.add_argument("--pilot", action="store_true",
                        help=f"Run on first {PILOT_N} problems only")
    parser.add_argument("--max_problems", type=int, default=None)
    args = parser.parse_args()

    records = prepare_mbpp_data()
    limit = PILOT_N if args.pilot else args.max_problems
    if limit:
        records = records[:limit]

    print(f"=== MBPP+ Run — {len(records)} problems ===")

    if args.system in ("single", "all"):
        run_single(records)
    if args.system in ("multi", "all"):
        run_multi(records)
    if args.system in ("v2", "all"):
        run_multi_v2(records)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
