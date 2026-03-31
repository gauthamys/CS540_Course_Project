"""
Coder node (CodeGen only).

Takes the plan, constraints, and critic feedback from state,
then produces the final code implementation.
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget
from src.llm.prompts.codegen_prompts import SYSTEM_CODEGEN
from src.schemas.codegen_schema import CodeSolution


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


CODER_ROLE = (
    "You are a Coder agent in a multi-agent code generation pipeline. "
    "A Planner has decomposed the problem and a Critic has reviewed a draft. "
    "Produce the final, corrected Python implementation."
)


def coder_node(state: dict) -> dict:
    """LangGraph node that produces final_code."""
    record = state["record"]
    plan = state.get("plan", "")
    constraints = state.get("constraints", [])
    draft_code = state.get("draft_code", "")
    critique = state.get("critique")
    test_result = state.get("test_result")
    repair_iteration = state.get("repair_iteration", 0)
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    constraints_str = "\n".join(f"- {c}" for c in constraints) if constraints else "None listed"

    if repair_iteration == 0:
        # First coding attempt — guided by plan and critic review
        user_prompt = (
            f"Problem (task_id: {record['id']}):\n\n{record['prompt']}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Constraints:\n{constraints_str}\n\n"
        )
        if critique:
            user_prompt += f"Critic feedback on draft:\n{critique}\n\n"
    else:
        # Repair attempt — guided by test failure output
        test_error = ""
        if test_result:
            test_error = test_result.get("error_output", "") or ""
        user_prompt = (
            f"Problem (task_id: {record['id']}):\n\n{record['prompt']}\n\n"
            f"Your previous implementation (attempt {repair_iteration}):\n"
            f"```python\n{draft_code}\n```\n\n"
            f"Failed with:\n{test_error}\n\n"
            f"Constraints to satisfy:\n{constraints_str}\n\n"
            "Fix the implementation."
        )

    user_prompt += (
        "\nRespond with JSON:\n"
        '{"task_id": "<id>", "code": "<raw Python only>", "explanation": "<what you did>"}'
    )

    structured_llm = _get_llm().with_structured_output(CodeSolution)
    try:
        solution = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_CODEGEN + "\n\n" + CODER_ROLE),
             HumanMessage(content=user_prompt)]
        )
        tokens = (len(user_prompt) + len(solution.code)) // 4
        return {
            "final_code": solution.code,
            "draft_code": solution.code,  # update draft for next repair iteration
            "repair_iteration": repair_iteration + 1,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        return {
            "final_code": draft_code or f"# coder_failure: {e}",
            "draft_code": draft_code or "",
            "repair_iteration": repair_iteration + 1,
            "llm_calls": 1,
            "total_tokens": 0,
        }
