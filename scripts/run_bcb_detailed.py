"""
Detailed single-agent run on first 5 BigCodeBench-Hard problems.

Flow per problem:
  1. Send instruct_prompt to Claude → get code
  2. Run unit tests directly (NO compile check)
  3. If fail → send repair prompt with test error back to Claude → retry
  4. Max 2 retries (3 total attempts)

Tracks full history of every attempt:
  - What prompt was sent to Claude
  - What code Claude returned
  - What the test result was
  - What error was seen

Outputs:
  outputs/single_agent_codegen/bcb/bcb_detailed_{timestamp}.json
"""
import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage

from src.datasets.bigcodebench_loader import load_bcb_first_n
from src.llm.client import get_structured_llm
from src.llm.prompts.codegen_prompts import SYSTEM_CODEGEN, format_codegen_prompt, format_codegen_repair_prompt
from src.schemas.codegen_schema import CodeSolution
from src.evaluation.codegen_metrics import run_single_test_bcb

OUTPUT_DIR = "outputs/single_agent_codegen/bcb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_RETRIES = 2  # 3 total attempts


def run_one(record: dict, llm) -> dict:
    """
    Run single-agent on one problem. Returns full attempt history.
    No compile check — goes straight to unit tests after each LLM call.
    """
    attempts = []
    messages = [SystemMessage(content=SYSTEM_CODEGEN), HumanMessage(content=format_codegen_prompt(record))]

    for attempt_num in range(1, MAX_RETRIES + 2):  # 1, 2, 3
        attempt_log = {
            "attempt_number": attempt_num,
            "prompt_sent":    messages[-1].content,  # last human message
            "code_returned":  None,
            "test_passed":    None,
            "test_error":     None,
            "action_taken":   None,
        }

        try:
            solution: CodeSolution = llm.invoke(messages)
            attempt_log["code_returned"] = solution.code

            # Run unit tests directly — no compile check
            test_result = run_single_test_bcb(
                code=solution.code,
                test_code=record["test_code"],
                task_id=record["id"],
                attempt=attempt_num,
            )
            attempt_log["test_passed"] = test_result.passed
            attempt_log["test_error"]  = test_result.error_output

            if test_result.passed:
                attempt_log["action_taken"] = "PASSED — stopping"
                attempts.append(attempt_log)
                return {
                    "task_id":     record["id"],
                    "final_code":  solution.code,
                    "passed":      True,
                    "total_attempts": attempt_num,
                    "attempts":    attempts,
                }

            # Failed — decide what to do next
            if attempt_num <= MAX_RETRIES:
                attempt_log["action_taken"] = f"FAILED — sending repair prompt (attempt {attempt_num + 1} next)"
                repair_prompt = format_codegen_repair_prompt(
                    record, solution.code, test_result.error_output or "tests failed"
                )
                messages = [SystemMessage(content=SYSTEM_CODEGEN), HumanMessage(content=repair_prompt)]
            else:
                attempt_log["action_taken"] = "FAILED — max retries reached, giving up"

            attempts.append(attempt_log)

        except Exception as e:
            attempt_log["code_returned"] = None
            attempt_log["test_passed"]   = False
            attempt_log["test_error"]    = f"LLM/parse error: {e}"
            attempt_log["action_taken"]  = f"PARSE ERROR — {'retrying' if attempt_num <= MAX_RETRIES else 'giving up'}"
            attempts.append(attempt_log)

            if attempt_num <= MAX_RETRIES:
                messages.append(HumanMessage(content=f"Validation error: {e}\nReturn valid JSON matching the schema."))

    return {
        "task_id":        record["id"],
        "final_code":     attempts[-1].get("code_returned") or "# generation_failed",
        "passed":         False,
        "total_attempts": MAX_RETRIES + 1,
        "attempts":       attempts,
    }



def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print("=== Single-Agent BCB-Hard Detailed Run (first 5) ===\n")

    print("Loading first 10 problems...")
    records = load_bcb_first_n(n=10)
    for r in records:
        print(f"  {r['id']} | libs: {r['libs']}")

    print("\nInitialising LLM...")
    llm = get_structured_llm(CodeSolution)

    all_results = []
    total = len(records)
    for i, rec in enumerate(records, 1):
        print(f"\n[{i}/{total}] Running {rec['id']}...")
        result = run_one(rec, llm)
        all_results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  → {status} in {result['total_attempts']} attempt(s)")

    # Save JSON report
    json_path = os.path.join(OUTPUT_DIR, f"bcb_detailed_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved -> {json_path}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
