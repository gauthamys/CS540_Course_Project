"""
RE SME (Subject Matter Expert) node — System 3 only.

Uses Claude with a dynamically constructed system prompt that adopts a domain-expert
persona identified by the planner. Generates additional requirements that a generalist
engineer might miss (compliance, domain standards, edge cases).

The SME node runs AFTER the extractor, receives draft_requirements as context,
and returns sme_requirements with source='sme'.
"""
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm, check_budget
from src.llm.prompts.re_elicitation_prompts import (
    format_sme_system_prompt,
    format_sme_prompt,
)
from src.schemas.re_elicitation_schema import GeneratedRequirement

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


class _RequirementsList(BaseModel):
    requirements: list[GeneratedRequirement]


def re_sme_node(state: dict) -> dict:
    """LangGraph node: generates domain-specific requirements via a Claude SME persona."""
    use_case = state["use_case_description"]
    domain = state.get("domain", "software")
    sme_subject = state.get("sme_subject", "software architect")
    draft_requirements = state.get("draft_requirements", [])
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    system_prompt = format_sme_system_prompt(domain=domain, sme_subject=sme_subject)
    user_prompt = format_sme_prompt(
        use_case=use_case,
        domain=domain,
        sme_subject=sme_subject,
        existing_requirements=draft_requirements,
    )

    structured_llm = _get_llm().with_structured_output(_RequirementsList)
    try:
        result: _RequirementsList = structured_llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        # Ensure all SME reqs have source='sme'
        sme_reqs = []
        for r in result.requirements:
            d = r.model_dump()
            d["source"] = "sme"
            sme_reqs.append(d)

        tokens = (len(user_prompt) + len(str(sme_reqs))) // 4
        return {
            "sme_requirements": sme_reqs,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception as e:
        # Fail-safe: return empty list, don't crash the pipeline
        return {
            "sme_requirements": [],
            "llm_calls": 1,
            "total_tokens": 0,
        }
