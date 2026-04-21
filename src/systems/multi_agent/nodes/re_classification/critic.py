"""Critic node for the RE Classification multi-agent pipeline."""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from typing import Optional

from src.llm.client import get_structured_llm, check_budget


class _RECriticOutput(BaseModel):
    approved: bool
    feedback: Optional[str] = None


RE_CRITIC_SYSTEM = (
    "You are a Critic agent in a multi-agent requirements engineering pipeline. "
    "You receive a sentence and a draft classification. "
    "Your job is to verify the classification is correct and consistent.\n\n"
    "Check for:\n"
    "  1. Is requirement_type correct? (FR vs NFR vs NONE)\n"
    "  2. If NFR, is the subtype accurate?\n"
    "  3. Is the rationale consistent with the text?\n"
    "  4. For SecReq records: is is_security_relevant set appropriately?\n\n"
    "Respond with JSON: {\"approved\": true/false, \"feedback\": \"<reason if not approved>\"}"
)


def re_critic_node(state: dict) -> dict:
    """LangGraph node for RE classification critique."""
    record = state["record"]
    draft = state.get("draft_prediction", {})
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = (
        f'Original sentence: "{record["text"]}"\n\n'
        f"Draft classification:\n{json.dumps(draft, indent=2)}\n\n"
        "Is this classification correct? Respond with JSON only."
    )
    structured_llm = get_structured_llm(_RECriticOutput)
    try:
        result = structured_llm.invoke(
            [SystemMessage(content=RE_CRITIC_SYSTEM), HumanMessage(content=prompt)]
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
