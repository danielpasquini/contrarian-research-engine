from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventCategory = Literal[
    "EARNINGS_REACTION",
    "GUIDANCE_CUT",
    "MACRO_SECTOR_SELLOFF",
    "REGULATORY_LEGAL",
    "ANALYST_DOWNGRADE",
    "MANAGEMENT_CHANGE",
    "NO_MATERIAL_NEWS",
    "OTHER",
]

FundamentalImpactType = Literal[
    "NONE",
    "TEMPORARY_1_2_QUARTERS",
    "STRUCTURAL_MULTI_YEAR",
    "UNKNOWN",
]

RedFlagType = Literal[
    "ACCOUNTING_IRREGULARITY",
    "SEC_DOJ_INVESTIGATION",
    "GOING_CONCERN_DISTRESS",
    "ABRUPT_CSUITE_EXIT",
    "COVENANT_BREACH",
    "IMMINENT_EARNINGS",
]


class CitedClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    is_new_information: bool = True


class LLMAnalysisOutput(BaseModel):
    """
    Validated Structured Output from Gemini Flash (`temperature=0.0`).
    Enforces fail-closed VETO if any structural red flag or structural multi-year
    deterioration is present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_id: UUID = Field(default_factory=uuid4)
    ticker: str
    model_id: str = "gemini-2.5-flash"
    prompt_version: str = "v1.0.0"
    input_cache_hash: str = ""
    event_classification: EventCategory
    verified_facts: list[CitedClaim] = Field(default_factory=list)
    market_narrative_summary: str
    fundamental_impact: FundamentalImpactType
    narrative_vs_filing_divergence: float = Field(ge=0.0, le=1.0)
    sentiment_inflection_detected: bool
    contradicting_evidence: list[CitedClaim] = Field(default_factory=list)
    red_flags_detected: list[RedFlagType] = Field(default_factory=list)
    veto_decision: Literal["APPROVE", "VETO"]
    confidence_score: float = Field(ge=0.0, le=1.0)
    missing_information: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_mandatory_red_flag_veto(self) -> "LLMAnalysisOutput":
        if (
            self.red_flags_detected
            or self.fundamental_impact == "STRUCTURAL_MULTI_YEAR"
            or self.confidence_score < 0.50
        ):
            object.__setattr__(self, "veto_decision", "VETO")
        return self
