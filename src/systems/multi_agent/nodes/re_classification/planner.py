"""Planner node for the RE Classification multi-agent pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


RE_PLANNER_SYSTEM = (
    "You are a Planner in a multi-agent requirements engineering pipeline. "
    "Your role is to analyze a sentence and decide the best strategy to classify it. "
    "Output a brief strategy (2-4 sentences) that will guide the Extractor agent. "
    "Do NOT produce the final classification — just the plan."
)


def re_planner_node(state: dict) -> dict:
    """LangGraph node for RE classification planning."""
    record = state["record"]
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = (
        f'Sentence to classify: "{record["text"]}"\n\n'
        f"Dataset: {record.get('source', 'unknown')}\n\n"
        "What is your strategy to classify this sentence? Consider:\n"
        "- Does it describe a system behavior (FR) or a quality attribute (NFR)?\n"
        "- Are there domain signals (e.g., security vocabulary, timing constraints)?\n"
        "- Could it be ambiguous? If so, what is the tiebreaker?"
    )
    response = _get_llm().invoke(
        [SystemMessage(content=RE_PLANNER_SYSTEM), HumanMessage(content=prompt)]
    )
    tokens = (len(prompt) + len(response.content)) // 4
    return {"plan": response.content, "llm_calls": 1, "total_tokens": tokens}
