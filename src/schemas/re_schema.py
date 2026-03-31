from pydantic import BaseModel, Field
from typing import Literal, Optional


class REPrediction(BaseModel):
    id: str = Field(description="Matches the input record id")
    requirement_type: Literal["FR", "NFR", "NONE"] = Field(
        description="Functional (FR), Non-functional (NFR), or not a requirement (NONE)"
    )
    nfr_subtype: Optional[
        Literal[
            "performance",
            "security",
            "usability",
            "reliability",
            "maintainability",
            "portability",
            "availability",
            "other",
        ]
    ] = Field(
        default=None,
        description="Only populated when requirement_type is NFR",
    )
    is_security_relevant: Optional[bool] = Field(
        default=None,
        description="Only populated for SecReq dataset records",
    )
    rationale: str = Field(
        description="Short explanation (1-2 sentences) for the classification"
    )


class REBatchOutput(BaseModel):
    predictions: list[REPrediction]
