"""
RE SME (Subject Matter Expert) advisory node — System 3 only.

Runs BEFORE the extractor. Uses Claude with a dynamically constructed system prompt
that adopts the domain-expert persona identified by the planner.

The SME does NOT generate requirements. Instead it produces structured advisory
context (constraints, patterns, risks) that is passed to the extractor to inform
more comprehensive requirement generation.

Graph flow (V2):
    planner → sme (advisory) → extractor (SME-informed) → critic → [revise loop]
"""
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_structured_llm, check_budget
from src.llm.prompts.re_elicitation_prompts import (
    format_sme_system_prompt,
    format_sme_advisory_prompt,
)
from src.schemas.re_elicitation_schema import SMEAdvisory


def re_sme_node(state: dict) -> dict:
    """LangGraph node: produces domain-expert advisory context for the extractor."""
    use_case = state["use_case_description"]
    domain = state.get("domain", "software")
    sme_subject = state.get("sme_subject", "software architect")
    key_quality_attributes = state.get("key_quality_attributes", [])
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)
    check_budget(llm_calls, total_tokens)

    system_prompt = format_sme_system_prompt(domain=domain, sme_subject=sme_subject)
    user_prompt = format_sme_advisory_prompt(
        use_case=use_case,
        domain=domain,
        sme_subject=sme_subject,
        key_quality_attributes=key_quality_attributes,
    )

    structured_llm = get_structured_llm(SMEAdvisory)
    try:
        advisory: SMEAdvisory = structured_llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        tokens = (len(system_prompt) + len(user_prompt) + len(str(advisory.model_dump()))) // 4
        return {
            "sme_advisory": advisory.advisory_summary,
            "sme_constraints": advisory.domain_constraints,
            "sme_patterns": advisory.common_requirement_patterns,
            "llm_calls": 1,
            "total_tokens": tokens,
        }
    except Exception:
        return {
            "sme_advisory": "",
            "sme_constraints": [],
            "sme_patterns": [],
            "llm_calls": 1,
            "total_tokens": 0,
        }
