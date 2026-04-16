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
        f"Generate up to 50 requirements. Be comprehensive — cover all major functional areas "
        f"and non-functional concerns. Keep each rationale to one sentence."
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
    sme_advisory: Optional[str] = None,
    sme_constraints: Optional[list[str]] = None,
    sme_patterns: Optional[list[str]] = None,
) -> str:
    qa_str = ", ".join(key_quality_attributes) if key_quality_attributes else "general quality"
    critique_block = (
        f"\nPREVIOUS CRITIQUE (address these gaps):\n{critique}\n"
        if critique
        else ""
    )
    sme_block = ""
    if sme_advisory or sme_constraints or sme_patterns:
        parts = ["\nDOMAIN EXPERT ADVISORY (incorporate this knowledge into your requirements):"]
        if sme_advisory:
            parts.append(f"  Summary: {sme_advisory}")
        if sme_constraints:
            parts.append("  Constraints to address:\n" + "\n".join(f"    - {c}" for c in sme_constraints))
        if sme_patterns:
            parts.append("  Requirement patterns to include:\n" + "\n".join(f"    - {p}" for p in sme_patterns))
        sme_block = "\n".join(parts)

    return (
        f"Generate a comprehensive list of software requirements for the following use case.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"ELICITATION STRATEGY:\n{strategy}\n\n"
        f"KEY QUALITY ATTRIBUTES TO COVER: {qa_str}"
        f"{sme_block}"
        f"{critique_block}\n\n"
        f"Return a JSON object with a single key 'requirements', whose value is a list of objects. "
        f"Each object must have:\n"
        f"  - req_id: string (e.g. 'R001')\n"
        f"  - text: string (the requirement)\n"
        f"  - type: 'FR' or 'NFR'\n"
        f"  - nfr_subtype: string or null (only for NFR)\n"
        f"  - source: 'main'\n"
        f"  - rationale: string (brief justification)\n\n"
        f"Generate up to 50 requirements. Be comprehensive — cover all major functional areas "
        f"and non-functional concerns. Keep each rationale to one sentence."
    )


# ── SME prompts ────────────────────────────────────────────────────────────────

def format_sme_system_prompt(domain: str, sme_subject: str) -> str:
    return (
        f"You are a {sme_subject} with deep expertise in the {domain} domain. "
        f"Your role is to advise a requirements engineer by sharing domain knowledge, "
        f"constraints, and patterns they should consider — not to write requirements yourself. "
        f"Output valid JSON only."
    )


def format_sme_advisory_prompt(
    use_case: str,
    domain: str,
    sme_subject: str,
    key_quality_attributes: list[str],
) -> str:
    qa_str = ", ".join(key_quality_attributes) if key_quality_attributes else "general quality"
    return (
        f"A requirements engineer is about to elicit requirements for the following {domain} system.\n\n"
        f"USE CASE DESCRIPTION:\n{use_case}\n\n"
        f"Quality attributes to consider: {qa_str}\n\n"
        f"As a {sme_subject}, provide advisory context to help the engineer produce a comprehensive "
        f"requirements list. Do NOT write requirements yourself — instead identify what constraints, "
        f"patterns, and risks the engineer should be aware of.\n\n"
        f"Return a JSON object with:\n"
        f"  - domain_constraints: list of strings — regulatory, compliance, or domain-specific "
        f"constraints the system must satisfy (e.g. 'Must comply with GDPR Article 17')\n"
        f"  - common_requirement_patterns: list of strings — typical requirement areas for {domain} "
        f"systems that a generalist might overlook (e.g. 'Audit logging for all data modifications')\n"
        f"  - risks_and_concerns: list of strings — domain risks or failure modes the requirements "
        f"should address (e.g. 'Data loss during network partition')\n"
        f"  - advisory_summary: string — 2-3 sentences of prose guidance for the extractor\n\n"
        f"Be specific and domain-precise. Aim for 3-8 items per list."
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
