from pydantic import BaseModel, Field
from typing import Optional


class CodeSolution(BaseModel):
    task_id: str = Field(description="Matches the input record id")
    code: str = Field(
        description="Complete Python function implementation. No markdown fencing, raw Python only."
    )
    explanation: str = Field(
        description="Brief explanation of approach and edge cases handled"
    )


class TestRunResult(BaseModel):
    task_id: str
    passed: bool
    num_passed: int
    num_total: int
    error_output: Optional[str] = None
    attempt_number: int
