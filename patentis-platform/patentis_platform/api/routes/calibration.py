from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import ExpertRating, TechnologyRegion, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.schemas.api import CalibrationOut, CalibrationSubmit

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.post("/rate", response_model=CalibrationOut)
async def submit_rating(
    body: CalibrationSubmit,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    reg = await session.get(TechnologyRegion, body.region_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Region not found")
    avg = (
        body.clinical_relevance
        + body.buildability
        + body.commercial_interest
        + body.whitespace_quality
    ) / 4.0
    rating = ExpertRating(
        id=uuid.uuid4(),
        org_id=user.org_id,
        region_id=body.region_id,
        user_id=user.id,
        clinical_relevance=body.clinical_relevance,
        buildability=body.buildability,
        commercial_interest=body.commercial_interest,
        whitespace_quality=body.whitespace_quality,
        notes=body.notes,
    )
    session.add(rating)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="calibration_rating",
        payload={
            "region_id": str(body.region_id),
            "clinical_relevance": body.clinical_relevance,
            "buildability": body.buildability,
            "commercial_interest": body.commercial_interest,
            "whitespace_quality": body.whitespace_quality,
            "avg_1_to_5": avg,
        },
        user_id=user.id,
        resource_type="technology_region",
        resource_id=str(body.region_id),
    )
    await write_audit(
        session,
        action="calibration.rate",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(body.region_id),
        detail={"avg": avg},
        commit=False,
    )
    await session.commit()
    return CalibrationOut(
        id=rating.id,
        region_id=rating.region_id,
        clinical_relevance=rating.clinical_relevance,
        buildability=rating.buildability,
        commercial_interest=rating.commercial_interest,
        whitespace_quality=rating.whitespace_quality,
    )


@router.get("/summary")
async def calibration_summary(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    res = await session.execute(
        select(func.count()).select_from(ExpertRating).where(ExpertRating.org_id == user.org_id)
    )
    count = res.scalar() or 0
    return {"ratings_count": count, "target": 100}
