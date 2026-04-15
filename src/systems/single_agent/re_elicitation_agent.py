"""
Single-agent RE Elicitation system (System 1).

Receives a use_case_description, makes one Claude call, returns a list of
GeneratedRequirement objects along with usage statistics.

Usage:
    agent = REElicitationAgent()
    requirements, usage = agent.elicit(project_id, use_case_description)
    # requirements: list[GeneratedRequirement]
    # usage: {"llm_calls": int, "total_tokens": int}
"""
import logging
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm
from src.llm.prompts.re_elicitation_prompts import (
    SYSTEM_RE_ELICITATION,
    format_elicitation_prompt,
)
from src.schemas.re_elicitation_schema import GeneratedRequirement

logger = logging.getLogger(__name__)


class _RequirementsList(BaseModel):
    requirements: list[GeneratedRequirement]


class REElicitationAgent:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self._llm = get_llm()
        self._structured_llm = self._llm.with_structured_output(_RequirementsList)

    def elicit(
        self, project_id: str, use_case_description: str
    ) -> tuple[list[dict], dict]:
        """
        Generate requirements for a single project.

        Returns:
            (requirements, usage_dict)
            requirements: list of GeneratedRequirement dicts
            usage_dict: {"llm_calls": int, "total_tokens": int}
        """
        user_prompt = format_elicitation_prompt(use_case_description)
        messages = [
            SystemMessage(content=SYSTEM_RE_ELICITATION),
            HumanMessage(content=user_prompt),
        ]

        total_calls = 0
        total_tokens = 0

        for attempt in range(self.max_retries + 1):
            try:
                response: _RequirementsList = self._structured_llm.invoke(messages)
                total_calls += 1
                total_tokens += (len(user_prompt) + len(str(response))) // 4
                reqs = [r.model_dump() for r in response.requirements]
                return reqs, {"llm_calls": total_calls, "total_tokens": total_tokens}
            except Exception as e:
                total_calls += 1
                logger.warning(
                    "Attempt %d failed for project %s: %s", attempt + 1, project_id, e
                )
                if attempt < self.max_retries:
                    messages.append(
                        HumanMessage(
                            content=(
                                f"Your previous response caused a validation error: {e}\n"
                                "Please try again and ensure your JSON exactly matches the schema."
                            )
                        )
                    )

        logger.error("All retries exhausted for project %s", project_id)
        return [], {"llm_calls": total_calls, "total_tokens": total_tokens}
