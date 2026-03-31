"""
Single-agent Requirements Engineering classifier.

Algorithm per record:
  1. Format prompt via re_prompts.py
  2. Call LLM with structured output (REPrediction via Pydantic)
  3. If validation fails, retry up to max_retries with the error appended
  4. On exhausted retries, return a NONE prediction with rationale="parse_failure"
  5. Log llm_calls and tokens to CostTracker
"""
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm
from src.llm.prompts.re_prompts import SYSTEM_RE, format_re_classify_prompt
from src.schemas.re_schema import REPrediction

logger = logging.getLogger(__name__)


class REAgent:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self._llm = get_llm()
        self._structured_llm = self._llm.with_structured_output(REPrediction)

    def classify(self, record: dict) -> tuple[REPrediction, dict]:
        """
        Classify a single RE record.

        Returns:
            (REPrediction, usage_dict)
            where usage_dict = {"llm_calls": int, "total_tokens": int}
        """
        user_prompt = format_re_classify_prompt(record)
        messages = [SystemMessage(content=SYSTEM_RE), HumanMessage(content=user_prompt)]

        total_calls = 0
        total_tokens = 0

        for attempt in range(self.max_retries + 1):
            try:
                response = self._structured_llm.invoke(messages)
                total_calls += 1
                # langchain-anthropic surfaces usage via response_metadata on the raw llm
                # When using with_structured_output we approximate token count
                total_tokens += _estimate_tokens(user_prompt, str(response))
                return response, {"llm_calls": total_calls, "total_tokens": total_tokens}
            except Exception as e:
                total_calls += 1
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, record.get("id"), e)
                if attempt < self.max_retries:
                    # Append error as a correction message and retry
                    messages.append(
                        HumanMessage(
                            content=(
                                f"Your previous response caused a validation error: {e}\n"
                                "Please try again and ensure your JSON exactly matches the schema."
                            )
                        )
                    )

        # All retries exhausted — return a safe default
        logger.error("All retries exhausted for record %s", record.get("id"))
        fallback = REPrediction(
            id=record.get("id", "unknown"),
            requirement_type="NONE",
            nfr_subtype=None,
            is_security_relevant=None,
            rationale="parse_failure",
        )
        return fallback, {"llm_calls": total_calls, "total_tokens": total_tokens}

    def classify_batch(self, records: list[dict]) -> tuple[list[REPrediction], dict]:
        """
        Classify a list of records. Returns (predictions, aggregated_usage).
        """
        predictions = []
        agg = {"llm_calls": 0, "total_tokens": 0}
        for record in records:
            pred, usage = self.classify(record)
            predictions.append(pred)
            agg["llm_calls"] += usage["llm_calls"]
            agg["total_tokens"] += usage["total_tokens"]
        return predictions, agg


def _estimate_tokens(prompt: str, response: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return (len(prompt) + len(response)) // 4
