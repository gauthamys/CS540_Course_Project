"""
Test Runner node (CodeGen only).

Executes final_code against the problem's test suite in a subprocess
with a timeout. Updates test_result in graph state.
The codegen graph routes back to the coder if tests fail and budget allows.
"""
import os

from src.evaluation.codegen_metrics import run_single_test
from src.utils.json_utils import strip_markdown_fences


MAX_REPAIR_ITERATIONS = int(os.getenv("MAX_REPAIR_ITERATIONS", "3"))


def test_runner_node(state: dict) -> dict:
    """LangGraph node that runs tests and records the result."""
    record = state["record"]
    final_code = state.get("final_code") or state.get("draft_code", "")
    repair_iteration = state.get("repair_iteration", 1)

    clean_code = strip_markdown_fences(final_code)
    test_code = record.get("test_code", "")

    result = run_single_test(
        code=clean_code,
        test_code=test_code,
        task_id=record["id"],
        attempt=repair_iteration,
    )

    return {"test_result": result.model_dump()}


def should_repair(state: dict) -> str:
    """
    Routing function after test_runner.
    Returns "repair" if tests failed and budget allows, "done" otherwise.
    """
    test_result = state.get("test_result", {})
    repair_iteration = state.get("repair_iteration", 1)
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)

    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))

    budget_ok = llm_calls < max_calls and total_tokens < max_tokens
    within_repair_limit = repair_iteration < MAX_REPAIR_ITERATIONS

    if test_result.get("passed", False):
        return "done"
    if budget_ok and within_repair_limit:
        return "repair"
    return "done"


# ---------------------------------------------------------------------------
# V2 — test_runner that respects augmented_test_code + routes to test_critic
# ---------------------------------------------------------------------------

def test_runner_v2_node(state: dict) -> dict:
    """
    V2 test runner: uses augmented_test_code if the test critic has enriched
    the suite, otherwise falls back to the original record test_code.
    Also increments repair_iteration so the coder knows it's a repair pass.
    """
    record = state["record"]
    final_code = state.get("final_code") or state.get("draft_code", "")
    repair_iteration = state.get("repair_iteration", 1)

    clean_code = strip_markdown_fences(final_code)
    # Prefer test-critic-augmented suite when available
    test_code = state.get("augmented_test_code") or record.get("test_code", "")

    result = run_single_test(
        code=clean_code,
        test_code=test_code,
        task_id=record["id"],
        attempt=repair_iteration,
    )

    return {
        "test_result": result.model_dump(),
        "repair_iteration": repair_iteration + 1,
    }


def should_repair_or_critique(state: dict) -> str:
    """
    Routing function for V2 after test_runner_v2_node.

    - Tests pass  → "critique"  (hand off to test_critic)
    - Tests fail + budget ok + within repair limit → "repair" (back to coder)
    - Otherwise   → "done"
    """
    test_result = state.get("test_result", {})
    repair_iteration = state.get("repair_iteration", 1)
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)

    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))

    budget_ok = llm_calls < max_calls and total_tokens < max_tokens
    within_repair_limit = repair_iteration < MAX_REPAIR_ITERATIONS

    if test_result.get("passed", False):
        return "critique"
    if budget_ok and within_repair_limit:
        return "repair"
    return "done"
