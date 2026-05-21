"""Admin ingestion: USPTO bulk XML, CPC graph, figure captioning."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_admin
from patentis_platform.db.models import User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.graph.build import rebuild_region_counts
from patentis_platform.graph.cpc_adjacency import expanded_ingest_prefixes
from patentis_platform.graph.queries import refresh_neighbor_avg_counts, seed_cpc_adjacency
from patentis_platform.ingestion.uspto_bulk import ingest_xml_path
from patentis_platform.multimodal.figure_captioner import caption_active_cpc_patents

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/uspto-bulk")
async def ingest_uspto_bulk(
    path: str = Query(..., description="Absolute path to XML file or directory on API host"),
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_admin),
):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=400, detail="Path not found on server")
    stats = await ingest_xml_path(session, p, vertical=vertical)
    await rebuild_region_counts(session)
    await write_audit(
        session,
        action="ingestion.uspto_bulk",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail=stats,
        commit=False,
    )
    await session.commit()
    return stats


@router.post("/cpc-graph/seed")
async def seed_graph(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_admin),
):
    n = await seed_cpc_adjacency(session)
    updated = await refresh_neighbor_avg_counts(session)
    await write_audit(
        session,
        action="ingestion.cpc_graph",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail={"edges": n, "regions_updated": updated},
        commit=False,
    )
    await session.commit()
    return {"edges_added": n, "regions_updated": updated, "ingest_prefixes": expanded_ingest_prefixes()}


@router.post("/figure-caption")
async def run_figure_captioning(
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_admin),
):
    n = await caption_active_cpc_patents(session, limit=limit)
    await write_audit(
        session,
        action="ingestion.figure_caption",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail={"patents": n},
        commit=False,
    )
    await session.commit()
    return {"captioned_patents": n}
