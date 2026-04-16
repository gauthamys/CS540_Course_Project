from typing import TypedDict, Optional, Annotated
from typing import List
import operator


class REGraphState(TypedDict):
    # Input
    record: dict
    dataset: str  # "nice" or "secreq"

    # Planner outputs
    plan: str

    # Extractor outputs
    draft_prediction: Optional[dict]  # REPrediction as dict before validation

    # Critic outputs
    critique: Optional[str]
    critique_approved: bool

    # Final output
    final_prediction: Optional[dict]

    # Bookkeeping (accumulated across nodes via reducer)
    llm_calls: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]
    iteration: int


class CodeGenGraphState(TypedDict):
    # Input
    record: dict

    # Planner outputs
    plan: str
    constraints: list[str]

    # Extractor / Coder outputs
    draft_code: Optional[str]

    # Critic outputs
    critique: Optional[str]
    critique_approved: bool

    # Final outputs
    final_code: Optional[str]
    test_result: Optional[dict]  # TestRunResult as dict

    # Repair loop counter
    repair_iteration: int

    # Bookkeeping (accumulated across nodes via reducer)
    llm_calls: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]


class CodeGenGraphStateV2(TypedDict):
    # Input
    record: dict

    # Planner outputs
    plan: str
    constraints: list[str]

    # Extractor / Coder outputs
    draft_code: Optional[str]

    # Critic outputs
    critique: Optional[str]
    critique_approved: bool

    # Final outputs
    final_code: Optional[str]
    test_result: Optional[dict]  # TestRunResult as dict

    # Repair loop counter
    repair_iteration: int

    # Test Critic outputs
    augmented_test_code: Optional[str]   # original tests + LLM-generated additions
    test_critique: Optional[str]         # feedback from test critic
    test_critique_approved: bool         # True when critic deems tests sufficient
    test_critique_iteration: int         # how many times test critic has run

    # Bookkeeping (accumulated across nodes via reducer)
    llm_calls: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]


class REElicitationState(TypedDict):
    # Input
    project_id: str
    use_case_description: str

    # Planner outputs
    plan: str
    domain: str
    sme_subject: str
    key_quality_attributes: List[str]

    # SME advisory outputs (System 3 only)
    # The SME provides domain knowledge to inform the extractor — not requirements
    sme_advisory: str          # prose guidance for the extractor
    sme_constraints: List[str] # domain-specific constraints/compliance concerns
    sme_patterns: List[str]    # common requirement patterns for this domain

    # Extractor outputs
    draft_requirements: List[dict]

    # Critic outputs
    critique: Optional[str]
    critique_approved: bool

    # Final output
    final_requirements: List[dict]

    # Bookkeeping (accumulated across nodes via reducer)
    llm_calls: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]
    iteration: int
