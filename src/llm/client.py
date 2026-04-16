"""
Central LLM client. All agent and node code should call through here
so that API configuration and cost tracking are centralized.
"""
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

MODEL_ID = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0  # deterministic for reproducibility


class BudgetExceededError(Exception):
    """Raised when a fairness budget (calls or tokens) is exhausted."""


def get_llm(max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE) -> ChatAnthropic:
    """Return a configured ChatAnthropic instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return ChatAnthropic(
        model=MODEL_ID,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def check_budget(llm_calls: int, total_tokens: int) -> None:
    """Raise BudgetExceededError if either fairness limit is hit."""
    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))
    if llm_calls >= max_calls:
        raise BudgetExceededError(f"LLM call budget exhausted ({llm_calls}/{max_calls})")
    if total_tokens >= max_tokens:
        raise BudgetExceededError(f"Token budget exhausted ({total_tokens}/{max_tokens})")
