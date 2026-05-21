from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.agents.orchestrator import (
    agent_feasibility_pass,
    agent_invention_brief,
    agent_risk_sketch,
    agent_whitespace_scan,
    ingest_cpc_sample,
    run_full_pipeline,
)
from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import Project, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.graph.cpc_adjacency import expanded_ingest_prefixes
from patentis_platform.ingestion.seed_medtech import run_seed
from patentis_platform.schemas.api import PatentIngestOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/ingest/seed")
async def seed(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    a, b = await run_seed()
    await write_audit(session, action="ingest.seed", org_id=user.org_id, actor_user_id=user.id, detail={"regions": a, "patents": b})
    return {"regions": a, "patents": b}


@router.post("/ingest/cpc-adjacent", response_model=dict)
async def ingest_adjacent_cpcs(
    limit_per_prefix: int = Query(30, le=80),
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    """Ingest patents for medtech CPC roots and one-hop adjacent subclasses."""
    user, _ = ctx
    total = 0
    for prefix in expanded_ingest_prefixes():
        n = await ingest_cpc_sample(session, prefix, limit=limit_per_prefix, vertical=vertical)
        total += n
    await write_audit(
        session,
        action="ingest.cpc_adjacent",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail={"imported": total, "prefixes": expanded_ingest_prefixes()},
    )
    return {"imported": total, "prefixes": expanded_ingest_prefixes()}


@router.post("/ingest/cpc/{prefix}", response_model=PatentIngestOut)
async def ingest_cpc(
    prefix: str,
    limit: int = Query(40, le=100),
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    n = await ingest_cpc_sample(session, prefix, limit=limit, vertical=vertical)
    await write_audit(session, action="ingest.cpc", org_id=user.org_id, actor_user_id=user.id, resource=prefix, detail={"imported": n})
    return PatentIngestOut(imported=n, skipped=0, vertical=vertical)


@router.get("/whitespace-scan")
async def whitespace_scan(
    vertical: str = Query("medtech"),
    top_n: int = Query(10, le=50),
    tenant_scores: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    org_id = user.org_id if tenant_scores else None
    return await agent_whitespace_scan(session, vertical, top_n, org_id=org_id)


@router.post("/feasibility/{region_id}")
async def feasibility(
    region_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _: tuple[User, str | None] = Depends(require_org_context),
):
    return await agent_feasibility_pass(session, region_id)


@router.post("/invention-brief/{project_id}/{region_id}")
async def invention_brief(
    project_id: UUID,
    region_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await agent_invention_brief(session, project_id, region_id, actor_user_id=user.id)


@router.post("/risk-sketch/{region_id}")
async def risk_sketch(
    region_id: UUID,
    idea_summary: str,
    session: AsyncSession = Depends(get_db_session),
    _: tuple[User, str | None] = Depends(require_org_context),
):
    return await agent_risk_sketch(session, region_id, idea_summary)


@router.post("/pipeline/{project_id}")
async def full_pipeline(
    project_id: UUID,
    idea_summary: str = "implantable sensor for micromotion",
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    out = await run_full_pipeline(session, project_id, vertical, idea_summary, actor_user_id=user.id)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="pipeline_run",
        payload={
            "vertical": vertical,
            "idea_summary": idea_summary[:800],
            "brief_generated": bool(out.get("brief")),
        },
        user_id=user.id,
        project_id=project_id,
    )
    await write_audit(
        session,
        action="agents.pipeline",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(project_id),
        commit=False,
    )
    await session.commit()
    return out
