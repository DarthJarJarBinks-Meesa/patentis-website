"""Refresh org-specific landscape scores into org_region_scores (uses org ML artifact)."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import OrgRegionScore, TechnologyRegion
from patentis_platform.scoring.models_ml import apply_saved_models


async def refresh_org_region_scores(session: AsyncSession, vertical: str, org_id: UUID) -> int:
    res = await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
    regions = list(res.scalars().all())
    scores = apply_saved_models(regions, org_id=str(org_id))
    if not scores:
        return 0

    for reg, s in zip(regions, scores):
        existing = await session.execute(
            select(OrgRegionScore).where(
                OrgRegionScore.org_id == org_id,
                OrgRegionScore.region_id == reg.id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = OrgRegionScore(
                id=uuid.uuid4(),
                org_id=org_id,
                region_id=reg.id,
            )
            session.add(row)
        row.isolation_forest_score = s["if"]
        row.rf_opportunity_score = s["rf"]
        row.composite_whitespace_score = s["composite"]

    await session.flush()
    return len(scores)
