from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class PatentHitOut(BaseModel):
    external_id: str
    title: str
    abstract: str
    url: str
    source: str
    assignee: Optional[str] = None


class PaperHitOut(BaseModel):
    external_id: str
    title: str
    abstract: str
    url: str
    source: str
    authors: list[str] = Field(default_factory=list)


class ProjectSearchResponse(BaseModel):
    project_id: str
    keywords: dict[str, Any]
    patents: list[PatentHitOut]
    papers: list[PaperHitOut]
    persisted: dict[str, int]


class MultimodalGapRequest(BaseModel):
    idea_hint: str = Field(default="", max_length=800)
    use_vision: bool = Field(
        default=False,
        description="Run vision captioning on claims-derived device semantics when API configured",
    )


class MultimodalGapResponse(BaseModel):
    region_id: str
    project_id: str
    cpc_subclass: str
    landscape: dict[str, Any]
    gaps_analysis: dict[str, Any]
    feasibility: dict[str, Any]
    modality_sources: list[str]
    disclaimer: str
