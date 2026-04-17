"""
Single-agent Code Generation agent.

Algorithm per record:
  1. Format prompt via codegen_prompts.py
  2. Call LLM with structured output (CodeSolution via Pydantic)
  3. Compile-check the returned code (no test execution at this stage)
  4. If compile fails and retries remain, send error back to LLM
  5. Return CodeSolution regardless of compile status (evaluation script judges correctness)
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
from src.utils.json_utils import strip_markdown_fences

logger = logging.getLogger(__name__)


class CodeGenAgent:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self._structured_llm = get_structured_llm(CodeSolution)

    def generate(self, record: dict) -> tuple[CodeSolution, dict]:
        """
        Generate code for a single problem.

        Returns:
            (CodeSolution, usage_dict)
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

                # Compile check
                compile_error = _compile_check(solution.code)
                if compile_error is None:
                    return solution, {"llm_calls": total_calls, "total_tokens": total_tokens}

                # Compile failed — repair if budget allows
                logger.warning(
                    "Attempt %d compile error for %s: %s",
                    attempt + 1, record.get("id"), compile_error,
                )
                if attempt < self.max_retries:
                    repair_prompt = format_codegen_repair_prompt(
                        record, solution.code, compile_error
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

        # Return last valid solution or fallback
        if last_solution is not None:
            return last_solution, {"llm_calls": total_calls, "total_tokens": total_tokens}

        fallback = CodeSolution(
            task_id=record.get("id", "unknown"),
            code="# generation_failed",
            explanation="All generation attempts failed.",
        )
        return fallback, {"llm_calls": total_calls, "total_tokens": total_tokens}

    def generate_batch(self, records: list[dict]) -> tuple[list[CodeSolution], dict]:
        solutions = []
        agg = {"llm_calls": 0, "total_tokens": 0}
        for record in records:
            sol, usage = self.generate(record)
            solutions.append(sol)
            agg["llm_calls"] += usage["llm_calls"]
            agg["total_tokens"] += usage["total_tokens"]
        return solutions, agg


def _compile_check(code: str) -> str | None:
    """
    Try to compile the code string. Returns the error message on failure, None on success.
    """
    clean = strip_markdown_fences(code)
    try:
        compile(clean, "<llm_output>", "exec")
        return None
    except SyntaxError as e:
        return f"SyntaxError: {e}"


def _estimate_tokens(prompt: str, response: str) -> int:
    return (len(prompt) + len(response)) // 4
