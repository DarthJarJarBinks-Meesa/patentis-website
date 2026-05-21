from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.multimodal.prior_art import prior_art_search
from patentis_platform.synthesis.keywords import extract_search_keywords

router = APIRouter(prefix="/prior-art", tags=["prior-art"])


@router.get("/search")
async def search_prior_art(
    q: str = Query(..., min_length=3, max_length=500),
    limit: int = Query(15, le=50),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    kw = await extract_search_keywords(q)
    terms = kw.get("keywords", []) + kw.get("broad_terms", [])
    out = await prior_art_search(q, keywords=terms, limit=limit)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="prior_art_search",
        payload={"query": q[:300], "total": out.get("total", 0)},
        user_id=user.id,
    )
    await write_audit(
        session,
        action="prior_art.search",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=q[:200],
        detail={"total": out.get("total")},
        commit=False,
    )
    await session.commit()
    return out
