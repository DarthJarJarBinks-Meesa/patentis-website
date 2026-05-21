"""Aggregate patent table into region-level statistics."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import PatentRecord, TechnologyRegion


async def rebuild_region_counts(session: AsyncSession, vertical: str = "medtech") -> None:
    """Update patent_count per region from PatentRecord.cpc_subclass."""
    counts = (
        await session.execute(
            select(PatentRecord.cpc_subclass, func.count().label("c"))
            .where(PatentRecord.cpc_subclass.isnot(None))
            .group_by(PatentRecord.cpc_subclass)
        )
    ).all()

    subclass_to_count = {row[0]: int(row[1]) for row in counts if row[0]}

    regions = (
        await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
    ).scalars().all()

    for reg in regions:
        if reg.cpc_subclass in subclass_to_count:
            reg.patent_count = subclass_to_count[reg.cpc_subclass]


async def ensure_region_for_subclass(session: AsyncSession, cpc: str, vertical: str = "medtech"):
    existing = await session.execute(
        select(TechnologyRegion).where(
            TechnologyRegion.cpc_subclass == cpc,
            TechnologyRegion.vertical == vertical,
        )
    )
    if existing.scalar_one_or_none():
        return
    session.add(
        TechnologyRegion(
            id=uuid.uuid4(),
            cpc_subclass=cpc,
            vertical=vertical,
            patent_count=0,
            neighbor_avg_count=5000,
            assignee_hhi=0.05,
            top_assignee_share=0.15,
            filing_growth_rate=0.1,
            citation_acceleration=0.05,
            pubmed_velocity=0.2,
            semantic_sparsity=0.3,
            scarcity_score=0.5,
            concentration_score=0.5,
            momentum_score=0.5,
        )
    )
