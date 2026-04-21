"""Planner node for the CodeGen multi-agent pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


CODEGEN_PLANNER_SYSTEM = (
    "You are a Planner in a multi-agent code generation pipeline. "
    "Your role is to decompose a programming problem into sub-goals and identify "
    "tricky constraints or edge cases. Output a brief plan (3-5 bullet points) "
    "and a list of constraints/edge cases. "
    "Do NOT write any code — just the plan."
)


def codegen_planner_node(state: dict) -> dict:
    """LangGraph node for CodeGen planning."""
    record = state["record"]
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = (
        f"Problem (task_id: {record['id']}):\n\n{record['prompt']}\n\n"
        "Produce:\n"
        "1. A step-by-step plan for implementing this function.\n"
        "2. A list of edge cases / tricky constraints to handle.\n\n"
        "Format your response as:\n"
        "PLAN:\n<bullet points>\n\nCONSTRAINTS:\n<bullet points>"
    )
    response = _get_llm().invoke(
        [SystemMessage(content=CODEGEN_PLANNER_SYSTEM), HumanMessage(content=prompt)]
    )
    tokens = (len(prompt) + len(response.content)) // 4
    constraints = _parse_constraints(response.content)
    return {
        "plan": response.content,
        "constraints": constraints,
        "llm_calls": 1,
        "total_tokens": tokens,
    }


def _parse_constraints(text: str) -> list[str]:
    """Extract bullet points after CONSTRAINTS: heading."""
    lines = text.split("\n")
    in_constraints = False
    constraints = []
    for line in lines:
        if "CONSTRAINTS:" in line.upper():
            in_constraints = True
            continue
        if in_constraints and line.strip().startswith(("-", "*", "•", "·")):
            constraints.append(line.strip().lstrip("-*•· ").strip())
        elif in_constraints and line.strip() and not line.strip().startswith(("-", "*", "•", "·")):
            if any(c.isupper() for c in line[:10]):
                break
    return constraints
