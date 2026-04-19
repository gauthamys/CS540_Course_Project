"""
Run the single-agent Code Generation system on HumanEval+.

Usage (from project root):
    python scripts/run_single_agent_codegen.py --mode pilot   # 10 problems
    python scripts/run_single_agent_codegen.py --mode full    # all ~164 problems

Outputs go to: outputs/single_agent_codegen/
  - codegen_solutions_{mode}_{timestamp}.jsonl   (generated code per problem)
  - codegen_tests_{mode}_{timestamp}.jsonl       (pass/fail + error per problem)
  - codegen_cost_{mode}_{timestamp}.json         (LLM call + token usage summary)
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.systems.single_agent.codegen_agent import CodeGenAgent
from src.evaluation.codegen_metrics import run_single_test, compute_codegen_metrics
from src.evaluation.cost_tracker import CostTracker

OUTPUT_DIR = "outputs/single_agent_codegen"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PILOT_PATH = "data/pilots/codegen_pilot10.jsonl"
FULL_PATH  = "data/processed/humaneval_plus.jsonl"


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


def run(records: list[dict], mode: str) -> None:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    total = len(records)

    print(f"\n[Single-Agent CodeGen] Running on {total} problems ({mode} mode)...")
    print("-" * 55)

    agent = CodeGenAgent(max_retries=2)
    tracker = CostTracker(system="single_agent_codegen", dataset=f"humaneval_{mode}")
    solutions = []
    test_results = []

    for i, rec in enumerate(records, 1):
        # Generate code (with internal compile + test retry loop)
        sol, usage = agent.generate(rec)

        # Final test run for official evaluation record
        test_result = run_single_test(
            code=sol.code,
            test_code=rec.get("test_code", ""),
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
        print(f"  [{i:3d}/{total}] {rec['id']:<25} -> {status}  ({usage['llm_calls']} LLM calls)")

    # Save outputs
    solutions_path = os.path.join(OUTPUT_DIR, f"codegen_solutions_{mode}_{timestamp}.jsonl")
    tests_path     = os.path.join(OUTPUT_DIR, f"codegen_tests_{mode}_{timestamp}.jsonl")
    cost_path      = os.path.join(OUTPUT_DIR, f"codegen_cost_{mode}_{timestamp}.json")

    write_jsonl(solutions, solutions_path)
    write_jsonl([r.model_dump() for r in test_results], tests_path)
    tracker.save(cost_path)

    # Print summary
    metrics = compute_codegen_metrics(test_results)
    summary = tracker.summary()
    print("\n" + "=" * 55)
    print(f"  pass@1            : {metrics['pass_at_1']:.1%}  ({int(metrics['pass_at_1'] * total)}/{total})")
    print(f"  compile error rate: {metrics['compile_error_rate']:.1%}")
    print(f"  avg tests passed  : {metrics['avg_tests_passed']:.1%}")
    print(f"  avg LLM calls     : {summary['avg_llm_calls']:.2f}")
    print(f"  total LLM calls   : {summary['total_llm_calls']}")
    print(f"  total tokens      : {summary['total_tokens']}")
    print("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-agent CodeGen runner")
    parser.add_argument(
        "--mode",
        choices=["pilot", "full"],
        default="pilot",
        help="pilot = 10 problems, full = all ~164 problems (default: pilot)",
    )
    args = parser.parse_args()

    data_path = PILOT_PATH if args.mode == "pilot" else FULL_PATH

    if not os.path.exists(data_path):
        print(f"ERROR: Data file not found: {data_path}")
        sys.exit(1)

    records = load_jsonl(data_path)
    print(f"=== Single-Agent CodeGen — {args.mode.upper()} RUN ===")
    run(records, mode=args.mode)
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
