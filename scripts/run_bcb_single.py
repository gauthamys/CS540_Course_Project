"""
Run the single-agent Code Generation system on BigCodeBench-Hard.

Usage (from project root):
    python scripts/run_bcb_single.py          # 5 random problems (default)
    python scripts/run_bcb_single.py --n 10   # any number up to 148

Outputs go to: outputs/single_agent_codegen/
  bcb_solutions_{n}_{timestamp}.jsonl
  bcb_tests_{n}_{timestamp}.jsonl
  bcb_cost_{n}_{timestamp}.json
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.datasets.bigcodebench_loader import sample_bcb_pilot
from src.systems.single_agent.codegen_agent import CodeGenAgent
from src.evaluation.codegen_metrics import run_single_test_bcb, compute_codegen_metrics
from src.evaluation.cost_tracker import CostTracker

OUTPUT_DIR = "outputs/single_agent_codegen"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def write_jsonl(records: list, path: str) -> None:
    with open(path, "w") as f:
        for r in records:
            obj = r if isinstance(r, dict) else r.model_dump()
            f.write(json.dumps(obj) + "\n")
    print(f"  Saved {len(records)} records -> {path}")


def run(n: int, seed: int) -> None:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print(f"\n[Single-Agent / BigCodeBench-Hard] Loading {n} random problems (seed={seed})...")
    records = sample_bcb_pilot(n=n, seed=seed)
    print(f"  Loaded: {[r['id'] for r in records]}")
    print("-" * 60)

    agent = CodeGenAgent(max_retries=2)
    tracker = CostTracker(system="single_agent_codegen", dataset=f"bcb_hard_{n}")
    solutions = []
    test_results = []

    for i, rec in enumerate(records, 1):
        sol, usage = agent.generate(rec)

        # Use BCB test runner (handles unittest.TestCase format)
        test_result = run_single_test_bcb(
            code=sol.code,
            test_code=rec["test_code"],
            task_id=rec["id"],
            attempt=usage["llm_calls"],
        )

        solutions.append(sol)
        test_results.append(test_result)
        tracker.record(
            llm_calls=usage["llm_calls"],
            total_tokens=usage["total_tokens"],
            task_id=rec["id"],
        )

        status = "PASS" if test_result.passed else "FAIL"
        error_hint = f"  -> {test_result.error_output[:80]}..." if not test_result.passed and test_result.error_output else ""
        print(f"  [{i}/{n}] {rec['id']:<30} -> {status}  ({usage['llm_calls']} LLM calls){error_hint}")

    # Save outputs
    solutions_path = os.path.join(OUTPUT_DIR, f"bcb_solutions_{n}_{timestamp}.jsonl")
    tests_path     = os.path.join(OUTPUT_DIR, f"bcb_tests_{n}_{timestamp}.jsonl")
    cost_path      = os.path.join(OUTPUT_DIR, f"bcb_cost_{n}_{timestamp}.json")

    write_jsonl(solutions, solutions_path)
    write_jsonl([r.model_dump() for r in test_results], tests_path)
    tracker.save(cost_path)

    # Summary
    metrics = compute_codegen_metrics(test_results)
    summary = tracker.summary()
    print("\n" + "=" * 60)
    print(f"  Dataset           : BigCodeBench-Hard ({n} problems)")
    print(f"  pass@1            : {metrics['pass_at_1']:.1%}  ({int(metrics['pass_at_1']*n)}/{n})")
    print(f"  compile error rate: {metrics['compile_error_rate']:.1%}")
    print(f"  avg LLM calls     : {summary['avg_llm_calls']:.2f}")
    print(f"  total tokens      : {summary['total_tokens']}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-agent on BigCodeBench-Hard")
    parser.add_argument("--n",    type=int, default=5,  help="Number of problems (default: 5)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    print("=== Single-Agent CodeGen — BigCodeBench-Hard ===")
    run(n=args.n, seed=args.seed)
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
