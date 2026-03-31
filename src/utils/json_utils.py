import json
import re


def strip_markdown_fences(text: str) -> str:
    """Remove ```python ... ``` or ``` ... ``` fences from a string."""
    text = re.sub(r"^```(?:python)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text.strip())
    return text.strip()


def safe_parse_json(text: str) -> dict:
    """
    Attempt to parse JSON from text. Strips markdown fences if present.
    Raises ValueError if parsing fails after stripping.
    """
    cleaned = strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nText was:\n{cleaned}") from e
