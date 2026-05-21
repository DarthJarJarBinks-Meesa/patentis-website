"""Discover CPC subgroups eligible for masked supervision."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.masking_config import MaskingConfig
from models.masking_pipeline import count_patents_for_subgroup, fetch_patents_for_subgroup
from patentis_platform.db.models import TechnologyRegion


async def eligible_cpc_subclasses(
    session: AsyncSession,
    config: MaskingConfig,
    vertical: str = "medtech",
) -> list[str]:
    """
    Subgroups = technology_regions.cpc_subclass rows with enough patents that have claims_text.
    """
    res = await session.execute(
        select(TechnologyRegion.cpc_subclass)
        .where(TechnologyRegion.vertical == vertical)
        .order_by(TechnologyRegion.cpc_subclass)
    )
    candidates = [row[0] for row in res.all()]
    eligible: list[str] = []
    for cpc in candidates:
        n = await count_patents_for_subgroup(session, cpc)
        if n >= config.min_region_size:
            eligible.append(cpc)
    return eligible


async def subgroup_patent_stats(
    session: AsyncSession,
    vertical: str = "medtech",
) -> list[dict]:
    res = await session.execute(
        select(TechnologyRegion).where(TechnologyRegion.vertical == vertical)
    )
    out = []
    for reg in res.scalars().all():
        total = await count_patents_for_subgroup(session, reg.cpc_subclass)
        with_claims = len(await fetch_patents_for_subgroup(session, reg.cpc_subclass))
        out.append(
            {
                "cpc_subclass": reg.cpc_subclass,
                "patent_count_region": reg.patent_count,
                "patents_in_subgroup": total,
                "patents_with_claims": with_claims,
            }
        )
    return out
