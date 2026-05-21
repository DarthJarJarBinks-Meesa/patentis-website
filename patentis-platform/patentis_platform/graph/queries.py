"""Graph queries: CPC neighbors, citation counts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import CpcAdjacency, PatentCitation, PatentRecord, TechnologyRegion
from patentis_platform.graph.cpc_adjacency import adjacent_subclasses, default_medtech_edges


async def seed_cpc_adjacency(session: AsyncSession) -> int:
    from patentis_platform.db.models import CpcAdjacency as CA
    import uuid

    n = 0
    for a, b, rel in default_medtech_edges():
        existing = await session.execute(
            select(CA).where(CA.from_subclass == a, CA.to_subclass == b)
        )
        if existing.scalar_one_or_none():
            continue
        session.add(CA(id=uuid.uuid4(), from_subclass=a, to_subclass=b, relation=rel))
        n += 1
    await session.flush()
    return n


async def get_adjacent_subclasses(session: AsyncSession, cpc: str) -> list[str]:
    res = await session.execute(
        select(CpcAdjacency.to_subclass).where(CpcAdjacency.from_subclass == cpc)
    )
    db_neighbors = list(res.scalars().all())
    static = adjacent_subclasses(cpc, include_self=False)
    return sorted(set(db_neighbors) | set(static))


async def refresh_neighbor_avg_counts(session: AsyncSession, vertical: str = "medtech") -> int:
    """Recompute TechnologyRegion.neighbor_avg_count from adjacent CPC patent counts."""
    res = await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
    regions = list(res.scalars().all())
    count_by_cpc: dict[str, int] = {}
    for reg in regions:
        count_by_cpc[reg.cpc_subclass] = reg.patent_count

    updated = 0
    for reg in regions:
        neighbors = await get_adjacent_subclasses(session, reg.cpc_subclass)
        if not neighbors:
            reg.neighbor_avg_count = float(reg.patent_count)
        else:
            vals = [count_by_cpc.get(n, 0) for n in neighbors]
            reg.neighbor_avg_count = sum(vals) / max(len(vals), 1)
        updated += 1
    await session.flush()
    return updated


async def citation_count_for_patent(session: AsyncSession, patent_id: UUID) -> int:
    res = await session.execute(
        select(func.count()).select_from(PatentCitation).where(PatentCitation.cited_patent_id == patent_id)
    )
    return int(res.scalar() or 0)


async def patents_in_cpc_family(session: AsyncSession, cpc: str, limit: int = 200) -> list[PatentRecord]:
    family = adjacent_subclasses(cpc, include_self=True)
    res = await session.execute(
        select(PatentRecord)
        .where(PatentRecord.cpc_subclass.in_(family))
        .limit(limit)
    )
    return list(res.scalars().all())
