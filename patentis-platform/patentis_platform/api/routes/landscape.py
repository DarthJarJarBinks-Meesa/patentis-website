from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.agents.orchestrator import agent_whitespace_scan, refresh_scores_if_models
from patentis_platform.api.deps import get_db_session, require_admin, require_org_context
from patentis_platform.db.models import TechnologyRegion, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.schemas.api import TechnologyRegionOut
from patentis_platform.scoring.org_region_refresh import refresh_org_region_scores
from patentis_platform.scoring.tenant_landscape import load_org_overlays, merge_region_scores

router = APIRouter(prefix="/landscape", tags=["landscape"])

_TENANT_LIST_CAP = 500


@router.get("/regions", response_model=list[TechnologyRegionOut])
async def list_regions(
    vertical: str = Query("medtech"),
    min_score: float | None = None,
    limit: int = Query(50, le=200),
    tenant_scores: bool = Query(False, description="Merge per-org ML overlays when trained"),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    if tenant_scores:
        res = await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
        rows = list(res.scalars().all())[:_TENANT_LIST_CAP]
        overlays = await load_org_overlays(session, user.org_id)
        merged = [merge_region_scores(r, overlays.get(r.id)) for r in rows]
        if min_score is not None:
            merged = [
                m
                for m in merged
                if (m.composite_whitespace_score is not None and m.composite_whitespace_score >= min_score)
            ]
        merged.sort(
            key=lambda m: m.composite_whitespace_score if m.composite_whitespace_score is not None else float("-inf"),
            reverse=True,
        )
        payload = merged[:limit]
    else:
        q = select(TechnologyRegion).where(TechnologyRegion.vertical == vertical)
        if min_score is not None:
            q = q.where(TechnologyRegion.composite_whitespace_score >= min_score)
        q = q.order_by(TechnologyRegion.composite_whitespace_score.desc().nulls_last()).limit(limit)
        res = await session.execute(q)
        rows = res.scalars().all()
        payload = [TechnologyRegionOut.model_validate(r, from_attributes=True) for r in rows]

    await write_audit(
        session,
        action="landscape.list",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=f"vertical:{vertical}",
        detail={"count": len(payload), "tenant_scores": tenant_scores},
        commit=False,
    )
    await session.commit()
    return payload


@router.get("/regions/{region_id}", response_model=TechnologyRegionOut)
async def get_region(
    region_id: UUID,
    tenant_scores: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    reg = await session.get(TechnologyRegion, region_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Region not found")
    if tenant_scores:
        overlays = await load_org_overlays(session, user.org_id)
        return merge_region_scores(reg, overlays.get(reg.id))
    return TechnologyRegionOut.model_validate(reg, from_attributes=True)


@router.post("/rescore")
async def rescore(
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    n = await refresh_scores_if_models(session, vertical)
    await write_audit(session, action="landscape.rescore", org_id=user.org_id, actor_user_id=user.id, detail={"n": n}, commit=False)
    await session.commit()
    return {"updated": n}


@router.post("/rescore-org")
async def rescore_org(
    vertical: str = Query("medtech"),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_admin),
):
    """Recompute tenant whitespace overlays from org-specific trained models (train.py --org-id)."""
    n = await refresh_org_region_scores(session, vertical, user.org_id)
    await write_audit(
        session,
        action="landscape.rescore_org",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail={"n": n, "vertical": vertical},
        commit=False,
    )
    await session.commit()
    return {"updated": n}


@router.get("/scan")
async def scan(
    vertical: str = Query("medtech"),
    top_n: int = Query(10, le=50),
    tenant_scores: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    org_id = user.org_id if tenant_scores else None
    return await agent_whitespace_scan(session, vertical, top_n=top_n, org_id=org_id)
