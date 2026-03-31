"""
Test Critic node (CodeGenV2 only).

Runs only when all existing tests pass. Evaluates whether the test suite
is thorough enough to catch bugs — checking for missing edge cases,
boundary values, and type variations.

If the critic deems the tests insufficient it generates additional test
cases (valid Python assert statements) that are appended to the existing
suite. The graph then routes back to test_runner with the augmented tests.
If the critic is satisfied it approves and the graph exits.

State fields read:   record, final_code, test_result, augmented_test_code,
                     test_critique_iteration, llm_calls, total_tokens
State fields written: augmented_test_code, test_critique,
                      test_critique_approved, test_critique_iteration,
                      llm_calls, total_tokens
"""
import os
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget
from src.utils.json_utils import strip_markdown_fences

logger = logging.getLogger(__name__)

MAX_TEST_CRITIQUE_ITERATIONS = int(os.getenv("MAX_TEST_CRITIQUE_ITERATIONS", "2"))

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


TEST_CRITIC_SYSTEM = """\
You are a Test Critic agent in a multi-agent code generation pipeline.

You receive:
  1. A problem description
  2. A Python implementation that currently passes all provided tests
  3. The test suite that was used

Your job is to decide whether the test suite is thorough enough to \
confidently verify correctness.

Look for gaps such as:
  - Empty / None / zero inputs
  - Single-element collections
  - Large or maximum-size inputs
  - Negative numbers, floats, or mixed types (where applicable)
  - Boundary values (off-by-one, min/max)
  - Repeated or duplicate elements
  - Cases that would expose common algorithmic mistakes

If the tests are sufficient respond ONLY with this JSON:
  {"approved": true, "feedback": "<brief reason>", "additional_tests": ""}

If the tests are insufficient respond ONLY with this JSON:
  {"approved": false, "feedback": "<what is missing>", "additional_tests": "<python code>"}

Rules for additional_tests:
  - Must be runnable Python placed AFTER the function definition
  - Use plain assert statements (no unittest, no pytest fixtures)
  - Each assert must include a descriptive comment on the same line
  - Do NOT redefine the function or import anything
  - Do NOT repeat tests that already exist
"""


def test_critic_node(state: dict) -> dict:
    """LangGraph node that critiques test coverage after all tests pass."""
    record = state["record"]
    final_code = state.get("final_code") or state.get("draft_code", "")
    iteration = state.get("test_critique_iteration", 0)
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)

    # Use augmented tests if already enriched, otherwise original
    current_tests = state.get("augmented_test_code") or record.get("test_code", "")

    try:
        check_budget(llm_calls, total_tokens)
    except Exception:
        return {
            "test_critique": "Budget exhausted — skipping test critique.",
            "test_critique_approved": True,
            "test_critique_iteration": iteration + 1,
            "llm_calls": 0,
            "total_tokens": 0,
        }

    prompt = (
        f"## Problem Description\n{record.get('prompt', '')}\n\n"
        f"## Implementation\n```python\n{final_code}\n```\n\n"
        f"## Existing Test Suite\n```python\n{current_tests}\n```\n\n"
        f"Evaluate the test suite. Respond with JSON only."
    )

    messages = [SystemMessage(content=TEST_CRITIC_SYSTEM), HumanMessage(content=prompt)]

    try:
        response = _get_llm().invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        token_est = (len(prompt) + len(raw)) // 4

        import json
        try:
            parsed = json.loads(strip_markdown_fences(raw))
        except Exception:
            # If JSON parse fails treat as approved to avoid infinite loop
            logger.warning("test_critic: failed to parse JSON response, approving.")
            return {
                "test_critique": raw,
                "test_critique_approved": True,
                "test_critique_iteration": iteration + 1,
                "llm_calls": 1,
                "total_tokens": token_est,
            }

        approved = bool(parsed.get("approved", True))
        feedback = parsed.get("feedback", "")
        additional = strip_markdown_fences(parsed.get("additional_tests", ""))

        new_test_code = current_tests
        if not approved and additional:
            new_test_code = current_tests.rstrip() + "\n\n# --- test_critic additions ---\n" + additional

        logger.info(
            "test_critic iter=%d approved=%s feedback=%s",
            iteration + 1, approved, feedback,
        )

        return {
            "augmented_test_code": new_test_code,
            "test_critique": feedback,
            "test_critique_approved": approved,
            "test_critique_iteration": iteration + 1,
            "llm_calls": 1,
            "total_tokens": token_est,
        }

    except Exception as e:
        logger.warning("test_critic error: %s", e)
        return {
            "test_critique": str(e),
            "test_critique_approved": True,   # fail-safe: don't block
            "test_critique_iteration": iteration + 1,
            "llm_calls": 1,
            "total_tokens": 0,
        }


def should_augment(state: dict) -> str:
    """
    Routing function after test_critic.
    Returns 'augment' to re-run tests with new cases, or 'done' to exit.
    """
    approved = state.get("test_critique_approved", True)
    iteration = state.get("test_critique_iteration", 0)
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)

    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))
    budget_ok = llm_calls < max_calls and total_tokens < max_tokens

    if approved or not budget_ok or iteration >= MAX_TEST_CRITIQUE_ITERATIONS:
        return "done"
    return "augment"
