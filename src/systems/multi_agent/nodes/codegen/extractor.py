"""Extractor node for the CodeGen multi-agent pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.codegen_prompts import SYSTEM_CODEGEN, format_codegen_prompt
from src.schemas.codegen_schema import CodeSolution


CODEGEN_EXTRACTOR_ROLE = (
    "You are an Extractor agent in a multi-agent code generation pipeline. "
    "A Planner has provided a strategy and list of constraints. "
    "Use these to produce a complete Python implementation."
)


def codegen_extractor_node(state: dict) -> dict:
    """LangGraph node for CodeGen — produces initial code draft."""
    record = state["record"]
    plan = state.get("plan", "")
    constraints = state.get("constraints", [])
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    system = SYSTEM_CODEGEN + "\n\n" + CODEGEN_EXTRACTOR_ROLE
    user_prompt = format_codegen_prompt(record)
    if plan:
        constraints_str = "\n".join(f"- {c}" for c in constraints) if constraints else "None listed"
        user_prompt = (
            f"Planner's approach:\n{plan}\n\nKey constraints:\n{constraints_str}\n\n"
            + user_prompt
        )

    structured_llm = get_structured_llm(CodeSolution)
    try:
        solution = structured_llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user_prompt)]
        )
        tokens = (len(user_prompt) + len(solution.code)) // 4
        return {
            "draft_code": solution.code,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        return {
            "draft_code": f"# extractor_failure: {e}",
            "llm_calls": 1,
            "total_tokens": 0,
        }
