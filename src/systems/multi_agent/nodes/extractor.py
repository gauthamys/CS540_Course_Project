"""
Extractor node.

For RE: produces a draft REPrediction guided by the Planner's strategy.
For CodeGen: produces a solution outline + initial code draft.

Both produce structured output (Pydantic models) stored in graph state.
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget
from src.llm.prompts.re_prompts import SYSTEM_RE, format_re_classify_prompt
from src.llm.prompts.codegen_prompts import SYSTEM_CODEGEN, format_codegen_prompt
from src.schemas.re_schema import REPrediction
from src.schemas.codegen_schema import CodeSolution


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# ── RE Extractor ──────────────────────────────────────────────────────────────

RE_EXTRACTOR_ROLE = (
    "You are an Extractor agent in a multi-agent requirements engineering pipeline. "
    "A Planner has already analyzed the sentence and provided a strategy. "
    "Use that strategy to produce the final classification."
)


def re_extractor_node(state: dict) -> dict:
    """LangGraph node for RE extraction (produces draft prediction)."""
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

    structured_llm = _get_llm().with_structured_output(REPrediction)
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
        # Fallback — return safe default
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


# ── CodeGen Extractor ─────────────────────────────────────────────────────────

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

    structured_llm = _get_llm().with_structured_output(CodeSolution)
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
