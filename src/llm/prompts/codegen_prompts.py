"""
Prompt templates for code generation tasks.

Shared between single-agent and multi-agent systems.
"""

SYSTEM_CODEGEN = (
    "You are an expert Python programmer. Given a programming problem, "
    "produce a complete, correct Python implementation.\n\n"
    "Rules:\n"
    "  - Return raw Python code only — no markdown fences, no explanations inside the code.\n"
    "  - The function signature must exactly match what is specified.\n"
    "  - Handle all edge cases mentioned in the problem.\n"
    "  - Do not include test code in your solution."
)


def format_codegen_prompt(record: dict) -> str:
    """
    Format the user-turn message for a single code generation problem.
    """
    return (
        f"Problem (task_id: {record['id']}):\n\n"
        f"{record['prompt']}\n\n"
        "Respond with a JSON object matching this schema:\n"
        "{\n"
        '  "task_id": "<task id>",\n'
        '  "code": "<complete Python implementation, no markdown>",\n'
        '  "explanation": "<brief explanation of your approach and edge cases>"\n'
        "}"
    )


def format_codegen_repair_prompt(record: dict, previous_code: str, error: str) -> str:
    """
    Format a repair prompt when the previous attempt failed tests.
    """
    return (
        f"Your previous solution for task {record['id']} failed with the following error:\n\n"
        f"{error}\n\n"
        f"Previous code:\n{previous_code}\n\n"
        "Fix the implementation and return the corrected JSON:\n"
        "{\n"
        '  "task_id": "<task id>",\n'
        '  "code": "<corrected Python implementation>",\n'
        '  "explanation": "<what you fixed and why>"\n'
        "}"
    )
