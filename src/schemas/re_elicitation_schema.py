from typing import Literal, Optional
from pydantic import BaseModel


class GeneratedRequirement(BaseModel):
    req_id: str
    text: str
    type: Literal["FR", "NFR"]
    nfr_subtype: Optional[str] = None
    source: Literal["main"] = "main"
    rationale: Optional[str] = None


class SMEAdvisory(BaseModel):
    """Domain-expert advisory context produced by the SME node.
    This informs the extractor but does NOT contain requirements directly.
    """
    domain_constraints: list[str]         # compliance/regulatory constraints
    common_requirement_patterns: list[str] # typical reqs for this domain an extractor should cover
    risks_and_concerns: list[str]          # domain risks a generalist might miss
    advisory_summary: str                  # 2-3 sentence prose guidance for the extractor


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
