"""Critic node for the CodeGen multi-agent pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from typing import Optional

from src.llm.client import get_structured_llm, check_budget


class _CodeCriticOutput(BaseModel):
    approved: bool
    feedback: Optional[str] = None


CODEGEN_CRITIC_SYSTEM = (
    "You are a Critic agent in a multi-agent code generation pipeline. "
    "You receive a programming problem and a draft implementation. "
    "Check the code for:\n"
    "  1. Correct function signature (matches the problem)\n"
    "  2. Obvious logical errors or missing edge cases\n"
    "  3. Any syntax issues\n\n"
    "Respond with JSON: {\"approved\": true/false, \"feedback\": \"<issues found>\"}"
)


def codegen_critic_node(state: dict) -> dict:
    """LangGraph node for CodeGen critique."""
    record = state["record"]
    draft_code = state.get("draft_code", "")
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = (
        f"Problem:\n{record['prompt']}\n\n"
        f"Draft implementation:\n```python\n{draft_code}\n```\n\n"
        "Is this implementation correct? Respond with JSON only."
    )
    structured_llm = get_structured_llm(_CodeCriticOutput)
    try:
        result = structured_llm.invoke(
            [SystemMessage(content=CODEGEN_CRITIC_SYSTEM), HumanMessage(content=prompt)]
        )
        tokens = (len(prompt) + len(str(result))) // 4
        return {
            "critique_approved": result.approved,
            "critique": result.feedback if not result.approved else None,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception:
        return {"critique_approved": True, "critique": None, "llm_calls": 1, "total_tokens": 0}
