from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TechnologyRegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cpc_subclass: str
    vertical: str
    patent_count: int
    scarcity_score: float
    concentration_score: float
    momentum_score: float
    isolation_forest_score: Optional[float] = None
    rf_opportunity_score: Optional[float] = None
    composite_whitespace_score: Optional[float] = None
    feasibility_score_cached: Optional[float] = None


class OpportunityBriefPayload(BaseModel):
    title: str
    gap_summary: str
    why_exists: str
    assignee_landscape: str
    enabling_science: str
    product_directions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    disclaimers: str = (
        "Decision support only — not legal advice. Inventorship requires human contribution."
    )


class OpportunityBriefOut(BaseModel):
    id: UUID
    project_id: UUID
    region_id: Optional[UUID]
    payload: dict[str, Any]
    citations: Optional[list[Any]] = None
    feasibility_score: Optional[float] = None
    withheld_low_feasibility: bool = False


class PatentIngestOut(BaseModel):
    imported: int
    skipped: int
    vertical: str


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    query: Optional[str] = None
    vertical: str = "medtech"


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    query: Optional[str]
    vertical: str


class CorpusUpload(BaseModel):
    title: str = ""
    body: str = Field(..., min_length=1)


class CalibrationSubmit(BaseModel):
    region_id: UUID
    clinical_relevance: int = Field(ge=1, le=5)
    buildability: int = Field(ge=1, le=5)
    commercial_interest: int = Field(ge=1, le=5)
    whitespace_quality: int = Field(ge=1, le=5)
    notes: Optional[str] = None


class CalibrationOut(BaseModel):
    id: UUID
    region_id: UUID
    clinical_relevance: int
    buildability: int
    commercial_interest: int
    whitespace_quality: int


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8)
    org_name: str = Field(default="My Lab")


class UserLogin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DPOFeedbackIn(BaseModel):
    region_id: UUID
    chosen_brief_id: UUID
    rejected_brief_id: UUID


class TrainingPolicyOut(BaseModel):
    base_sft: str
    org_lora: str
    opt_out: str
    retention_days_after_opt_out: int = 30


class TrainingStatusOut(BaseModel):
    training_opt_in: bool
    training_opt_out_at: Optional[str] = None
    training_data_purge_after: Optional[str] = None
    adapter_status: str = "none"
    adapter_version: Optional[str] = None
    adapter_blob_path: Optional[str] = None
    inference: dict[str, Any] = Field(default_factory=dict)


class OrgProfileOut(BaseModel):
    org_id: UUID
    org_name: str
    plan: str
    profile: dict[str, Any] = Field(default_factory=dict)
    training_opt_in: bool = False
    training_data_purge_after: Optional[str] = None


class OrgProfilePatch(BaseModel):
    profile: Optional[dict[str, Any]] = None
    plan: Optional[str] = Field(default=None, description="standard | enterprise")
    training_opt_in: Optional[bool] = None
    training_opt_in_acknowledged: Optional[bool] = Field(
        default=None,
        description="Required true when enabling training_opt_in",
    )
