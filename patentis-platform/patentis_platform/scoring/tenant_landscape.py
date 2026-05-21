"""Merge shared TechnologyRegion rows with per-org whitespace score overlays."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import OrgRegionScore, TechnologyRegion
from patentis_platform.schemas.api import TechnologyRegionOut


async def load_org_overlays(session: AsyncSession, org_id: UUID) -> dict[UUID, OrgRegionScore]:
    res = await session.execute(select(OrgRegionScore).where(OrgRegionScore.org_id == org_id))
    return {row.region_id: row for row in res.scalars().all()}


def merge_region_scores(reg: TechnologyRegion, overlay: OrgRegionScore | None) -> TechnologyRegionOut:
    """Prefer tenant overlay IF/RF/composite when present; base features stay global."""
    return TechnologyRegionOut(
        id=reg.id,
        cpc_subclass=reg.cpc_subclass,
        vertical=reg.vertical,
        patent_count=reg.patent_count,
        scarcity_score=reg.scarcity_score,
        concentration_score=reg.concentration_score,
        momentum_score=reg.momentum_score,
        isolation_forest_score=(
            overlay.isolation_forest_score
            if overlay is not None and overlay.isolation_forest_score is not None
            else reg.isolation_forest_score
        ),
        rf_opportunity_score=(
            overlay.rf_opportunity_score
            if overlay is not None and overlay.rf_opportunity_score is not None
            else reg.rf_opportunity_score
        ),
        composite_whitespace_score=(
            overlay.composite_whitespace_score
            if overlay is not None and overlay.composite_whitespace_score is not None
            else reg.composite_whitespace_score
        ),
        feasibility_score_cached=reg.feasibility_score_cached,
    )


def effective_composite(reg: TechnologyRegion, overlay: OrgRegionScore | None) -> float:
    if overlay is not None and overlay.composite_whitespace_score is not None:
        return float(overlay.composite_whitespace_score)
    if reg.composite_whitespace_score is not None:
        return float(reg.composite_whitespace_score)
    return float("-inf")
