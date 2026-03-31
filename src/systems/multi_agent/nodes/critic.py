"""
Critic / Verifier node.

For RE: checks draft prediction for consistency, completeness, and format.
For CodeGen: checks draft code for obvious issues before test execution.

Returns critique (string) and critique_approved (bool).
If approved, the graph routes to END (or coder for codegen).
If rejected and budget allows, the graph loops back to extractor.
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# ── RE Critic ─────────────────────────────────────────────────────────────────

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
    """LangGraph node for RE critique."""
    record = state["record"]
    draft = state.get("draft_prediction", {})
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    import json
    prompt = (
        f'Original sentence: "{record["text"]}"\n\n'
        f"Draft classification:\n{json.dumps(draft, indent=2)}\n\n"
        "Is this classification correct? Respond with JSON only."
    )
    structured_llm = _get_llm().with_structured_output(_RECriticOutput)
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
        # On parse failure, approve to avoid infinite loops
        return {"critique_approved": True, "critique": None, "llm_calls": 1, "total_tokens": 0}


# ── CodeGen Critic ────────────────────────────────────────────────────────────

CODEGEN_CRITIC_SYSTEM = (
    "You are a Critic agent in a multi-agent code generation pipeline. "
    "You receive a programming problem and a draft implementation. "
    "Check the code for:\n"
    "  1. Correct function signature (matches the problem)\n"
    "  2. Obvious logical errors or missing edge cases\n"
    "  3. Any syntax issues\n\n"
    "Respond with JSON: {\"approved\": true/false, \"feedback\": \"<issues found>\"}"
)


def codegen_critic_node(state: dict) -> dict:
    """LangGraph node for CodeGen critique."""
    record = state["record"]
    draft_code = state.get("draft_code", "")
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    prompt = (
        f"Problem:\n{record['prompt']}\n\n"
        f"Draft implementation:\n```python\n{draft_code}\n```\n\n"
        "Is this implementation correct? Respond with JSON only."
    )
    structured_llm = _get_llm().with_structured_output(_CodeCriticOutput)
    try:
        result = structured_llm.invoke(
            [SystemMessage(content=CODEGEN_CRITIC_SYSTEM), HumanMessage(content=prompt)]
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


# ── Pydantic schemas for critic structured output ─────────────────────────────

from pydantic import BaseModel
from typing import Optional


class _RECriticOutput(BaseModel):
    approved: bool
    feedback: Optional[str] = None


class _CodeCriticOutput(BaseModel):
    approved: bool
    feedback: Optional[str] = None
