"""Aggregate expert calibration targets per organization (tenant-isolated)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import ExpertRating


async def fetch_org_region_labels(session: AsyncSession, org_id: UUID) -> dict[UUID, float]:
    """Mean expert label per region in [0,1], scoped to one organization."""
    total = (
        ExpertRating.clinical_relevance
        + ExpertRating.buildability
        + ExpertRating.commercial_interest
        + ExpertRating.whitespace_quality
    )
    stmt = (
        select(ExpertRating.region_id, func.avg(total / 20.0))
        .where(ExpertRating.org_id == org_id)
        .group_by(ExpertRating.region_id)
    )
    res = await session.execute(stmt)
    return {row[0]: float(row[1]) for row in res.all()}
