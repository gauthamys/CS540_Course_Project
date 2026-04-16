"""
RE Elicitation Critic node.

Receives a use case description and the current requirements list (draft or combined),
returns a CriticVerdict: approved or feedback + missing_types.

Used by System 2 (V1) and System 3 (V2+SME).
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.re_elicitation_prompts import format_critic_prompt
from src.schemas.re_elicitation_schema import CriticVerdict

CRITIC_SYSTEM = (
    "You are a requirements quality critic. "
    "Assess whether a requirements list adequately covers the given use case. "
    "Output valid JSON only."
)


def re_elicitation_critic_node(state: dict) -> dict:
    """LangGraph node: critiques the current requirements list."""
    use_case = state["use_case_description"]
    # For System 3, use combined_requirements if available; otherwise draft_requirements
    requirements = (
        state.get("combined_requirements")
        or state.get("draft_requirements")
        or []
    )
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = format_critic_prompt(use_case=use_case, requirements=requirements)
    structured_llm = get_structured_llm(CriticVerdict)

    try:
        result: CriticVerdict = structured_llm.invoke(
            [SystemMessage(content=CRITIC_SYSTEM), HumanMessage(content=prompt)]
        )
        tokens = (len(prompt) + len(str(result))) // 4
        return {
            "critique_approved": result.approved,
            "critique": result.feedback if not result.approved else None,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception:
        # On parse failure, approve to avoid infinite loops
        return {
            "critique_approved": True,
            "critique": None,
            "llm_calls": 1,
            "total_tokens": 0,
        }
