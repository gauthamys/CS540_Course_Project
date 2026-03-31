"""
Planner node — decomposes the task and returns a short strategy string.

For RE: identifies domain-specific signals (security language, performance
  constraints) and decides which subtype taxonomy to apply.
For CodeGen: decomposes the problem into sub-goals and lists tricky edge cases.

The planner's output lives in state['plan'] and is passed downstream to
the extractor and coder nodes.
"""
import os
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# ── RE Planner ────────────────────────────────────────────────────────────────

RE_PLANNER_SYSTEM = (
    "You are a Planner in a multi-agent requirements engineering pipeline. "
    "Your role is to analyze a sentence and decide the best strategy to classify it. "
    "Output a brief strategy (2-4 sentences) that will guide the Extractor agent. "
    "Do NOT produce the final classification — just the plan."
)


def re_planner_node(state: dict) -> dict:
    """LangGraph node for RE planning."""
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


# ── CodeGen Planner ───────────────────────────────────────────────────────────

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

    # Parse constraints from the response
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
            # Stop at next non-bullet section
            if any(c.isupper() for c in line[:10]):
                break
    return constraints
