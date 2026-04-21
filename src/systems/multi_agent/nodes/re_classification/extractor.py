"""Extractor node for the RE Classification multi-agent pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.re_prompts import SYSTEM_RE, format_re_classify_prompt
from src.schemas.re_schema import REPrediction


RE_EXTRACTOR_ROLE = (
    "You are an Extractor agent in a multi-agent requirements engineering pipeline. "
    "A Planner has already analyzed the sentence and provided a strategy. "
    "Use that strategy to produce the final classification."
)


def re_extractor_node(state: dict) -> dict:
    """LangGraph node for RE classification extraction."""
    record = state["record"]
    plan = state.get("plan", "")
    critique = state.get("critique")
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    system = SYSTEM_RE + "\n\n" + RE_EXTRACTOR_ROLE
    user_prompt = format_re_classify_prompt(record)
    if plan:
        user_prompt = f"Planner strategy:\n{plan}\n\n" + user_prompt
    if critique:
        user_prompt += f"\n\nCritic feedback (previous draft was rejected):\n{critique}\nPlease revise accordingly."

    structured_llm = get_structured_llm(REPrediction)
    try:
        prediction = structured_llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user_prompt)]
        )
        tokens = (len(user_prompt) + len(str(prediction))) // 4
        return {
            "draft_prediction": prediction.model_dump(),
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        fallback = REPrediction(
            id=record.get("id", "unknown"),
            requirement_type="NONE",
            nfr_subtype=None,
            is_security_relevant=None,
            rationale=f"extractor_failure: {e}",
        )
        return {
            "draft_prediction": fallback.model_dump(),
            "llm_calls": 1,
            "total_tokens": 0,
        }
