"""
Prompt templates for the RE Elicitation systems (single-agent and multi-agent).
All three systems draw from this shared module to keep prompts consistent.
"""
from typing import Optional

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_RE_ELICITATION = (
    "You are a senior requirements engineer. "
    "You produce structured, unambiguous software requirements. "
    "Classify each requirement as FR (functional) or NFR (non-functional). "
    "For NFR, add the most specific subtype from: "
    "performance, security, usability, reliability, maintainability, portability, availability. "
    "Use 'other' only if none fit. "
    "Output valid JSON only — no prose outside the JSON structure."
)


# ── Single-agent prompt ────────────────────────────────────────────────────────

def format_elicitation_prompt(use_case: str) -> str:
    return (
        f"Given the following software project use case description, generate a comprehensive "
        f"list of software requirements.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"Return a JSON object with a single key 'requirements', whose value is a list of objects. "
        f"Each object must have:\n"
        f"  - req_id: string (e.g. 'R001')\n"
        f"  - text: string (the requirement)\n"
        f"  - type: 'FR' or 'NFR'\n"
        f"  - nfr_subtype: string or null (only for NFR)\n"
        f"  - source: 'main'\n"
        f"  - rationale: string (brief justification)\n\n"
        f"Generate between 8 and 20 requirements. Cover both functional and non-functional concerns."
    )


# ── Planner prompt ─────────────────────────────────────────────────────────────

SYSTEM_PLANNER = (
    "You are a requirements planning expert. "
    "Your job is to analyse a software use case and produce a structured elicitation plan "
    "that will guide a requirements extractor. "
    "Output valid JSON only."
)


def format_planner_prompt(use_case: str) -> str:
    return (
        f"Analyse the following software use case and produce a requirements elicitation plan.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"Return a JSON object with these fields:\n"
        f"  - domain: string (e.g. 'healthcare', 'e-commerce', 'banking')\n"
        f"  - sme_subject: string (a specific expert role whose domain knowledge would add value, "
        f"e.g. 'HIPAA compliance officer', 'payment security auditor')\n"
        f"  - strategy: string (2-4 sentences: what the extractor should focus on)\n"
        f"  - key_quality_attributes: list of strings (3-6 NFR categories most relevant, "
        f"e.g. ['security', 'performance', 'reliability'])"
    )


# ── Extractor prompt ───────────────────────────────────────────────────────────

def format_extractor_prompt(
    use_case: str,
    strategy: str,
    key_quality_attributes: list[str],
    critique: Optional[str] = None,
) -> str:
    qa_str = ", ".join(key_quality_attributes) if key_quality_attributes else "general quality"
    critique_block = (
        f"\nPREVIOUS CRITIQUE (address these gaps):\n{critique}\n"
        if critique
        else ""
    )
    return (
        f"Generate a comprehensive list of software requirements for the following use case.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"ELICITATION STRATEGY:\n{strategy}\n\n"
        f"KEY QUALITY ATTRIBUTES TO COVER: {qa_str}"
        f"{critique_block}\n\n"
        f"Return a JSON object with a single key 'requirements', whose value is a list of objects. "
        f"Each object must have:\n"
        f"  - req_id: string (e.g. 'R001')\n"
        f"  - text: string (the requirement)\n"
        f"  - type: 'FR' or 'NFR'\n"
        f"  - nfr_subtype: string or null (only for NFR)\n"
        f"  - source: 'main'\n"
        f"  - rationale: string (brief justification)\n\n"
        f"Generate between 8 and 20 requirements."
    )


# ── SME prompt ─────────────────────────────────────────────────────────────────

def format_sme_system_prompt(domain: str, sme_subject: str) -> str:
    return (
        f"You are a {sme_subject} with deep expertise in the {domain} domain. "
        f"Your role is to identify requirements that a generalist requirements engineer might miss — "
        f"especially domain-specific compliance, risk, and quality concerns. "
        f"Output valid JSON only."
    )


def format_sme_prompt(
    use_case: str,
    domain: str,
    sme_subject: str,
    existing_requirements: list[dict],
) -> str:
    existing_texts = "\n".join(
        f"  - [{r.get('type','?')}] {r.get('text','')}" for r in existing_requirements
    )
    return (
        f"A generalist engineer has already produced the following requirements for a {domain} system:\n\n"
        f"{existing_texts}\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"As a {sme_subject}, identify ADDITIONAL requirements that the above list is missing. "
        f"Focus on {domain}-specific concerns: compliance, domain standards, edge cases a non-expert would overlook.\n\n"
        f"Return a JSON object with a single key 'requirements', whose value is a list of objects. "
        f"Each object must have:\n"
        f"  - req_id: string (e.g. 'SME001')\n"
        f"  - text: string (the requirement)\n"
        f"  - type: 'FR' or 'NFR'\n"
        f"  - nfr_subtype: string or null (only for NFR)\n"
        f"  - source: 'sme'\n"
        f"  - rationale: string (why a {sme_subject} considers this important)\n\n"
        f"Generate between 3 and 10 additional requirements. Do NOT repeat requirements already in the list above."
    )


# ── Critic prompt ──────────────────────────────────────────────────────────────

def format_critic_prompt(use_case: str, requirements: list[dict]) -> str:
    reqs_str = "\n".join(
        f"  [{r.get('req_id','?')}] [{r.get('type','?')}] {r.get('text','')}"
        for r in requirements
    )
    return (
        f"You are a requirements quality critic. Review the following requirements list "
        f"against the use case description and assess completeness and correctness.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"REQUIREMENTS:\n{reqs_str}\n\n"
        f"Return a JSON object with:\n"
        f"  - approved: boolean (true if requirements are sufficient)\n"
        f"  - missing_types: list of strings describing what is missing "
        f"(e.g. ['NFR:security', 'FR:user-login']); empty list if approved\n"
        f"  - feedback: string with specific actionable guidance, or null if approved\n\n"
        f"Approve if: there are at least 6 requirements, both FR and NFR are present, "
        f"and no obvious functional area from the use case is unaddressed."
    )


# ── Use-case synthesis prompt (for prepare_re_elicitation.py) ─────────────────

SYSTEM_USE_CASE_SYNTHESIS = (
    "You are a business analyst. Given a list of software requirements for a project, "
    "write a concise use case description (3-6 sentences) that describes WHAT the software system does "
    "and WHO uses it — without referencing the individual requirements. "
    "Write in plain prose, no bullet points, no headers."
)


def format_use_case_synthesis_prompt(project_id: str, requirements: list[dict]) -> str:
    reqs_str = "\n".join(
        f"  - [{r.get('label','?')}] {r.get('text','')}" for r in requirements
    )
    return (
        f"Project ID: {project_id}\n\n"
        f"Requirements ({len(requirements)} total):\n{reqs_str}\n\n"
        f"Write a concise use case description (3-6 sentences) for this software system. "
        f"Describe what the system does and who its users are. Do not list requirements."
    )
