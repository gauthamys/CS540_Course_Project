from typing import Literal, Optional
from pydantic import BaseModel


class GeneratedRequirement(BaseModel):
    req_id: str
    text: str
    type: Literal["FR", "NFR"]
    nfr_subtype: Optional[str] = None
    source: Literal["main", "sme"] = "main"  # "sme" = from SME node
    rationale: Optional[str] = None


class REElicitationOutput(BaseModel):
    project_id: str
    requirements: list[GeneratedRequirement]
    system: Literal["single_agent", "multi_agent_v1", "multi_agent_v2_sme"]


class PlannerOutput(BaseModel):
    domain: str                          # e.g. "healthcare"
    sme_subject: str                     # e.g. "HIPAA compliance officer"
    strategy: str                        # 2-4 sentence guidance for extractor
    key_quality_attributes: list[str]    # e.g. ["security", "reliability"]


class CriticVerdict(BaseModel):
    approved: bool
    missing_types: list[str]             # e.g. ["NFR:security", "FR:login"]
    feedback: Optional[str] = None
