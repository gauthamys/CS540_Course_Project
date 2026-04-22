"""
Central LLM client. All agent and node code should call through here
so that API configuration and cost tracking are centralized.

Supports both Claude (Anthropic) and local Ollama models.
Switch via USE_LOCAL_LLM env var.
"""
import os
import json
import logging
from dotenv import load_dotenv
from langchain_core.runnables import Runnable

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_ID = "claude-sonnet-4-6"
LOCAL_MODEL_ID = os.getenv("LOCAL_MODEL_ID", "mistral-nemo")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MAX_TOKENS = 16384
DEFAULT_TEMPERATURE = 0  # deterministic for reproducibility



class BudgetExceededError(Exception):
    """Raised when a fairness budget (calls or tokens) is exhausted."""


class OllamaStructuredOutput(Runnable):
    """
    Wrapper for Ollama that parses JSON output into Pydantic models.

    Since Ollama doesn't support .with_structured_output(), we:
    1. Call the LLM normally (prompts already request JSON)
    2. Extract and parse JSON from the response
    3. Validate against the schema
    """
    def __init__(self, llm, schema):
        self.llm = llm
        self.schema = schema

    def invoke(self, input, config=None):
        """Call LLM and parse response as schema."""
        response_text = self.llm.invoke(input)
        return self._parse_json(response_text)

    async def ainvoke(self, input, config=None):
        """Async version."""
        response_text = await self.llm.ainvoke(input)
        return self._parse_json(response_text)

    def _parse_json(self, text: str):
        """Extract JSON from text and validate against schema."""
        # Try to extract JSON from markdown fences first
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        # Try to find JSON object in the text
        if not text.strip().startswith("{"):
            # Find first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end+1]

        try:
            data = json.loads(text)
            return self.schema(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from response: {e}\nResponse: {text[:200]}")
        except Exception as e:
            raise ValueError(f"Failed to validate response against schema: {e}\nData: {data}")



def get_llm(max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE):
    """
    Return either Claude or local Ollama based on USE_LOCAL_LLM env var.

    Set USE_LOCAL_LLM=true to use local model.
    Default: Claude API
    """
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

    if use_local:
        try:
            from langchain_community.llms import Ollama
            return Ollama(
                model=LOCAL_MODEL_ID,
                base_url=OLLAMA_BASE_URL,
                temperature=temperature,
            )
        except ImportError:
            raise ImportError(
                "langchain-community is required for local LLM support. "
                "Run: pip install langchain-community"
            )
    else:
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return ChatAnthropic(
            model=MODEL_ID,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )


def get_structured_llm(schema, max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE):
    """
    Return an LLM that enforces structured output via the given Pydantic schema.

    For Claude: uses .with_structured_output()
    For Ollama: uses OllamaStructuredOutput wrapper with JSON parsing
    """
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    llm = get_llm(max_tokens=max_tokens, temperature=temperature)

    if use_local:
        logger.info(f"Using Ollama with JSON parsing fallback for {schema.__name__}")
        return OllamaStructuredOutput(llm, schema)
    else:
        logger.info(f"Using Claude with native structured output for {schema.__name__}")
        return llm.with_structured_output(schema)



def check_budget(llm_calls: int, total_tokens: int) -> None:
    """Raise BudgetExceededError if either fairness limit is hit."""
    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "100000"))
    if llm_calls >= max_calls:
        raise BudgetExceededError(f"LLM call budget exhausted ({llm_calls}/{max_calls})")
    if total_tokens >= max_tokens:
        raise BudgetExceededError(f"Token budget exhausted ({total_tokens}/{max_tokens})")
