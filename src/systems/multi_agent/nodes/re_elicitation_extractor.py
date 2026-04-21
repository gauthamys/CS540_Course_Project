"""
RE Elicitation Extractor node.

Generates a draft list of requirements (GeneratedRequirement) from the use case,
guided by the planner's strategy and any critic feedback.

Used by System 2 (V1) and System 3 (V2+SME).
"""
import os
from typing import Optional
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.re_elicitation_prompts import (
    SYSTEM_RE_ELICITATION,
    format_extractor_prompt,
)
from src.schemas.re_elicitation_schema import GeneratedRequirement


class _RequirementsList(BaseModel):
    requirements: list[GeneratedRequirement]


def re_elicitation_extractor_node(state: dict) -> dict:
    """LangGraph node: generates draft requirements from use case + planner strategy."""
    use_case = state["use_case_description"]
    strategy = state.get("plan", "")
    key_quality_attributes = state.get("key_quality_attributes", [])
    critique: Optional[str] = state.get("critique")
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens, max_tokens=int(os.getenv("RE_MAX_TOKENS_PER_TASK", "30000")))

    # SME advisory context (present in V2 only; None/empty in V1)
    sme_advisory: Optional[str] = state.get("sme_advisory") or None
    sme_constraints: list = state.get("sme_constraints") or []
    sme_patterns: list = state.get("sme_patterns") or []

    prompt = format_extractor_prompt(
        use_case=use_case,
        strategy=strategy,
        key_quality_attributes=key_quality_attributes,
        critique=critique,
        sme_advisory=sme_advisory,
        sme_constraints=sme_constraints,
        sme_patterns=sme_patterns,
    )

    structured_llm = get_structured_llm(_RequirementsList)
    try:
        result: _RequirementsList = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_RE_ELICITATION), HumanMessage(content=prompt)]
        )
        reqs = [r.model_dump() for r in result.requirements]
        tokens = (len(prompt) + len(str(reqs))) // 4
        return {
            "draft_requirements": reqs,
            "critique": None,  # clear previous critique after revision
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        return {
            "draft_requirements": [],
            "llm_calls": 1,
            "total_tokens": 0,
        }
