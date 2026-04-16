"""
RE Elicitation Planner node.

Receives a use_case_description and returns structured planning output:
  - domain, sme_subject, strategy, key_quality_attributes

Used by both System 2 (multi_agent V1) and System 3 (multi_agent V2 + SME).
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.re_elicitation_prompts import SYSTEM_PLANNER, format_planner_prompt
from src.schemas.re_elicitation_schema import PlannerOutput


def re_elicitation_planner_node(state: dict) -> dict:
    """LangGraph node: plans RE elicitation strategy from use case description."""
    use_case = state["use_case_description"]
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = format_planner_prompt(use_case)
    structured_llm = get_structured_llm(PlannerOutput)

    try:
        result: PlannerOutput = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PLANNER), HumanMessage(content=prompt)]
        )
        tokens = (len(prompt) + len(str(result))) // 4
        return {
            "plan": result.strategy,
            "domain": result.domain,
            "sme_subject": result.sme_subject,
            "key_quality_attributes": result.key_quality_attributes,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        return {
            "plan": f"planner_failure: {e}",
            "domain": "software",
            "sme_subject": "software architect",
            "key_quality_attributes": ["security", "performance", "reliability"],
            "llm_calls": 1,
            "total_tokens": 0,
        }
