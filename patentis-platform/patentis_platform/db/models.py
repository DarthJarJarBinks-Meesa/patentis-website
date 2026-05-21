import uuid
from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from patentis_platform.db.base import Base

EMBED_DIM = 384  # all-MiniLM-L6-v2


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="standard")  # standard | enterprise
    profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    training_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    training_opt_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    training_opt_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    training_data_purge_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    lora_adapter: Mapped[Optional["OrgLoRAAdapter"]] = relationship(
        back_populates="organization", uselist=False
    )


class OrgLoRAAdapter(Base):
    """
    Per-org private LoRA weights in org-scoped blob storage.
    Never merged into base Patentis-SFT; loaded only for requests from that org.
    """

    __tablename__ = "org_lora_adapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="none"
    )  # none | training | active | retired | purge_pending
    blob_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped["Organization"] = relationship(back_populates="lora_adapter")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(64), default="member")  # admin | member | expert
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Project(Base):
    """Org-scoped workspace (Harvey Vault equivalent)."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vertical: Mapped[str] = mapped_column(String(64), default="medtech")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    corpus_items: Mapped[list["CorpusDocument"]] = relationship(back_populates="project")


class TechnologyRegion(Base):
    """CPC subclass (or node) × vertical with engineered features + scores."""

    __tablename__ = "technology_regions"
    __table_args__ = (UniqueConstraint("cpc_subclass", "vertical", name="uq_region_vertical"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpc_subclass: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    vertical: Mapped[str] = mapped_column(String(64), index=True, default="medtech")

    patent_count: Mapped[int] = mapped_column(Integer, default=0)
    neighbor_avg_count: Mapped[float] = mapped_column(Float, default=0.0)
    assignee_hhi: Mapped[float] = mapped_column(Float, default=0.0)
    top_assignee_share: Mapped[float] = mapped_column(Float, default=0.0)
    filing_growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    citation_acceleration: Mapped[float] = mapped_column(Float, default=0.0)
    pubmed_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_sparsity: Mapped[float] = mapped_column(Float, default=0.0)

    scarcity_score: Mapped[float] = mapped_column(Float, default=0.0)
    concentration_score: Mapped[float] = mapped_column(Float, default=0.0)
    momentum_score: Mapped[float] = mapped_column(Float, default=0.0)

    isolation_forest_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rf_opportunity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    composite_whitespace_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    expert_calibration_label: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feasibility_score_cached: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    feature_version: Mapped[str] = mapped_column(String(32), default="v1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class OrgRegionScore(Base):
    """Per-tenant whitespace scores over shared TechnologyRegion rows (enterprise isolation)."""

    __tablename__ = "org_region_scores"
    __table_args__ = (UniqueConstraint("org_id", "region_id", name="uq_org_region_score"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("technology_regions.id"), index=True)

    isolation_forest_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rf_opportunity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    composite_whitespace_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PatentRecord(Base):
    __tablename__ = "patents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, default="")
    claims_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cpc_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    cpc_subclass: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="patentsview")
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(EMBED_DIM), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PatentFigure(Base):
    """Vision-derived figure captions linked to claim numbers."""

    __tablename__ = "patent_figures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patents.id"), index=True)
    figure_num: Mapped[str] = mapped_column(String(32), default="1")
    caption: Mapped[str] = mapped_column(Text, default="")
    claim_refs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    image_blob_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CpcAdjacency(Base):
    """Directed CPC neighbor edges for related-subclass landscape expansion."""

    __tablename__ = "cpc_adjacency"
    __table_args__ = (UniqueConstraint("from_subclass", "to_subclass", name="uq_cpc_adj"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_subclass: Mapped[str] = mapped_column(String(32), index=True)
    to_subclass: Mapped[str] = mapped_column(String(32), index=True)
    relation: Mapped[str] = mapped_column(String(32), default="sibling")  # parent | child | sibling


class MaskingRunRecord(Base):
    """Self-supervised masking run audit + SFT dataset accumulation."""

    __tablename__ = "masking_run_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpc_subclass: Mapped[str] = mapped_column(String(32), index=True)
    strategy: Mapped[str] = mapped_column(String(32))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    record_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PatentCitation(Base):
    __tablename__ = "patent_citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citing_patent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patents.id"))
    cited_patent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patents.id"))


class CorpusDocument(Base):
    """User / project uploaded or pinned patent text chunks."""

    __tablename__ = "corpus_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    source_type: Mapped[str] = mapped_column(String(32), default="upload")  # upload | patent | note
    title: Mapped[str] = mapped_column(String(512), default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="corpus_items")


class OpportunityBrief(Base):
    __tablename__ = "opportunity_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    region_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technology_regions.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    citations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    feasibility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    withheld_low_feasibility: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ExpertRating(Base):
    """Human labels for calibration / future DPO — scoped per organization."""

    __tablename__ = "expert_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("technology_regions.id"))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    clinical_relevance: Mapped[int] = mapped_column(Integer, default=0)  # 1-5
    buildability: Mapped[int] = mapped_column(Integer, default=0)
    commercial_interest: Mapped[int] = mapped_column(Integer, default=0)
    whitespace_quality: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    api_key_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    detail_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DPOFeedback(Base):
    """Preference pairs for future DPO / ranking fine-tune — scoped per organization."""

    __tablename__ = "dpo_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("technology_regions.id"))
    chosen_brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunity_briefs.id"))
    rejected_brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunity_briefs.id"))
    annotator_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class InteractionSignal(Base):
    """Tenant-private telemetry for personalization datasets and org-scoped model improvement."""

    __tablename__ = "interaction_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
