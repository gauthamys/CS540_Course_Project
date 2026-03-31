"""
Prompt templates for Requirements Engineering classification.

Both the single-agent and multi-agent systems share the same SYSTEM_RE
and task description to satisfy the fairness controls in the proposal.
Role framing (e.g., "You are a Planner...") is added on top by each
system, but the core task description never differs.
"""

SYSTEM_RE = (
    "You are an expert requirements engineer with deep knowledge of software "
    "requirement classification. Your task is to classify sentences from software "
    "specifications.\n\n"
    "Classification labels:\n"
    "  FR   – Functional Requirement: describes what the system shall do "
    "(a specific behavior, function, or capability).\n"
    "  NFR  – Non-Functional Requirement: describes a quality attribute or constraint "
    "(e.g., performance, security, usability, reliability, maintainability, "
    "portability, availability).\n"
    "  NONE – Not a requirement: a statement that does not express a system "
    "requirement (e.g., a definition, rationale, assumption, or heading).\n\n"
    "When classifying as NFR, also identify the subtype from this list: "
    "performance, security, usability, reliability, maintainability, portability, "
    "availability, other."
)


def format_re_classify_prompt(record: dict) -> str:
    """
    Format the user-turn message for classifying a single RE record.
    Works for both NICE and SecReq datasets.
    """
    text = record["text"]
    dataset = record.get("source", "")

    secreq_note = ""
    if dataset == "secreq":
        secreq_note = (
            "\n\nAdditionally, set is_security_relevant to true if this sentence "
            "is related to security (even if it is not an NFR/security requirement), "
            "otherwise false."
        )

    return (
        f'Classify the following sentence:\n\n"{text}"\n\n'
        f"Record id: {record['id']}{secreq_note}\n\n"
        "Respond with a JSON object matching this schema:\n"
        "{\n"
        '  "id": "<record id>",\n'
        '  "requirement_type": "FR" | "NFR" | "NONE",\n'
        '  "nfr_subtype": "<subtype or null>",\n'
        '  "is_security_relevant": true | false | null,\n'
        '  "rationale": "<1-2 sentence explanation>"\n'
        "}"
    )
