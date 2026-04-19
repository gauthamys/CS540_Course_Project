"""
Single-agent Code Generation agent.

Algorithm per record:
  1. Format prompt from record (problem + function signature)
  2. Call LLM with structured output (CodeSolution via Pydantic)
  3. Compile-check the returned code (syntax only)
     - FAIL: send repair prompt to LLM, spend 1 retry from shared pool
     - PASS: proceed to unit tests
  4. Run actual unit tests via subprocess
     - PASS: return CodeSolution + usage
     - FAIL: send repair prompt with test error, spend 1 retry from shared pool
  5. Shared retry pool of max_retries=2 (spent across compile AND test failures)
  6. If all retries exhausted: return last valid solution or fallback
"""
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm
from src.llm.prompts.codegen_prompts import (
    SYSTEM_CODEGEN,
    format_codegen_prompt,
    format_codegen_repair_prompt,
)
from src.schemas.codegen_schema import CodeSolution
from src.evaluation.codegen_metrics import run_single_test
from src.utils.json_utils import strip_markdown_fences

logger = logging.getLogger(__name__)


class CodeGenAgent:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self._structured_llm = get_structured_llm(CodeSolution)

    def generate(self, record: dict) -> tuple[CodeSolution, dict]:
        """
        Generate code for a single problem with compile + unit test feedback loop.

        Shared retry pool: compile failures and test failures both draw from
        the same max_retries budget. E.g. with max_retries=2:
          - compile fail on attempt 1, test fail on attempt 2 -> attempt 3 is last chance
          - compile fail twice -> no retries left for tests

        Returns:
            (CodeSolution, usage_dict)  where usage_dict has llm_calls and total_tokens
        """
        user_prompt = format_codegen_prompt(record)
        messages = [SystemMessage(content=SYSTEM_CODEGEN), HumanMessage(content=user_prompt)]

        total_calls = 0
        total_tokens = 0
        last_solution: CodeSolution | None = None

        for attempt in range(self.max_retries + 1):
            try:
                solution = self._structured_llm.invoke(messages)
                total_calls += 1
                total_tokens += _estimate_tokens(user_prompt, solution.code)
                last_solution = solution

                # --- Stage 1: compile check (syntax only) ---
                compile_error = _compile_check(solution.code)
                if compile_error is not None:
                    logger.warning(
                        "Attempt %d compile error for %s: %s",
                        attempt + 1, record.get("id"), compile_error,
                    )
                    if attempt < self.max_retries:
                        repair_prompt = format_codegen_repair_prompt(
                            record, solution.code, f"Syntax error: {compile_error}"
                        )
                        messages = [
                            SystemMessage(content=SYSTEM_CODEGEN),
                            HumanMessage(content=repair_prompt),
                        ]
                    continue  # spend this retry, try again

                # --- Stage 2: run actual unit tests ---
                test_result = run_single_test(
                    code=solution.code,
                    test_code=record.get("test_code", ""),
                    task_id=record.get("id", "unknown"),
                    attempt=attempt + 1,
                )

                if test_result.passed:
                    logger.info("Attempt %d PASSED tests for %s", attempt + 1, record.get("id"))
                    return solution, {"llm_calls": total_calls, "total_tokens": total_tokens}

                # Tests failed
                logger.warning(
                    "Attempt %d test failure for %s: %s",
                    attempt + 1, record.get("id"), test_result.error_output,
                )
                if attempt < self.max_retries:
                    repair_prompt = format_codegen_repair_prompt(
                        record, solution.code, test_result.error_output or "tests failed"
                    )
                    messages = [
                        SystemMessage(content=SYSTEM_CODEGEN),
                        HumanMessage(content=repair_prompt),
                    ]

            except Exception as e:
                total_calls += 1
                logger.warning("Attempt %d parse error for %s: %s", attempt + 1, record.get("id"), e)
                if attempt < self.max_retries:
                    messages.append(
                        HumanMessage(
                            content=(
                                f"Your previous response caused a validation error: {e}\n"
                                "Please fix and return valid JSON matching the schema."
                            )
                        )
                    )

        # All retries exhausted — return last valid solution or fallback
        if last_solution is not None:
            return last_solution, {"llm_calls": total_calls, "total_tokens": total_tokens}

        fallback = CodeSolution(
            task_id=record.get("id", "unknown"),
            code="# generation_failed",
            explanation="All generation attempts failed.",
        )
        return fallback, {"llm_calls": total_calls, "total_tokens": total_tokens}

    def generate_batch(self, records: list[dict]) -> tuple[list[CodeSolution], dict]:
        """Run generate() on each record, aggregate usage."""
        solutions = []
        agg = {"llm_calls": 0, "total_tokens": 0}
        for record in records:
            sol, usage = self.generate(record)
            solutions.append(sol)
            agg["llm_calls"] += usage["llm_calls"]
            agg["total_tokens"] += usage["total_tokens"]
        return solutions, agg


def _compile_check(code: str) -> str | None:
    """Syntax-check code. Returns error string on failure, None on success."""
    clean = strip_markdown_fences(code)
    try:
        compile(clean, "<llm_output>", "exec")
        return None
    except SyntaxError as e:
        return f"SyntaxError: {e}"


def _estimate_tokens(prompt: str, response: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return (len(prompt) + len(response)) // 4
