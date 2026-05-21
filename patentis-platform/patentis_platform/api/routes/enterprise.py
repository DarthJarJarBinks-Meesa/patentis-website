from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_admin, require_org_context
from patentis_platform.db.models import AuditLog, DPOFeedback, InteractionSignal, Organization, User
from patentis_platform.enterprise.access import require_brief_in_org
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.enterprise.opt_out import apply_training_opt_out
from patentis_platform.enterprise.org_adapters import ensure_adapter_row
from patentis_platform.schemas.api import DPOFeedbackIn, OrgProfileOut, OrgProfilePatch

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


@router.get("/account", response_model=OrgProfileOut)
async def get_account(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    org = await session.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgProfileOut(
        org_id=org.id,
        org_name=org.name,
        plan=org.plan,
        profile=dict(org.profile_json or {}),
        training_opt_in=bool(org.training_opt_in),
        training_data_purge_after=(
            org.training_data_purge_after.isoformat() if org.training_data_purge_after else None
        ),
    )


@router.patch("/account", response_model=OrgProfileOut)
async def patch_account(
    body: OrgProfilePatch,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
    _: User = Depends(require_admin),
):
    user, _ = ctx
    org = await session.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.plan is not None:
        if body.plan not in ("standard", "enterprise"):
            raise HTTPException(status_code=400, detail="plan must be standard or enterprise")
        org.plan = body.plan
    if body.profile is not None:
        merged = {**(org.profile_json or {}), **body.profile}
        org.profile_json = merged
    if body.training_opt_in is not None:
        if body.training_opt_in and not body.training_opt_in_acknowledged:
            raise HTTPException(
                status_code=400,
                detail="Set training_opt_in_acknowledged=true to confirm org LoRA policy",
            )
        if body.training_opt_in and not org.training_opt_in:
            from datetime import datetime, timezone

            org.training_opt_in = True
            org.training_opt_in_at = datetime.now(timezone.utc)
            org.training_opt_out_at = None
            org.training_data_purge_after = None
            await ensure_adapter_row(session, org.id)
        elif not body.training_opt_in and org.training_opt_in:
            await apply_training_opt_out(session, org.id)
        else:
            org.training_opt_in = body.training_opt_in
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="org_profile_updated",
        payload={
            "plan": body.plan,
            "profile_keys": list(body.profile.keys()) if body.profile else [],
        },
        user_id=user.id,
    )
    await write_audit(
        session,
        action="enterprise.account.patch",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(org.id),
        commit=False,
    )
    await session.commit()
    await session.refresh(org)
    return OrgProfileOut(
        org_id=org.id,
        org_name=org.name,
        plan=org.plan,
        profile=dict(org.profile_json or {}),
        training_opt_in=bool(org.training_opt_in),
        training_data_purge_after=(
            org.training_data_purge_after.isoformat() if org.training_data_purge_after else None
        ),
    )


@router.get("/interactions")
async def list_interactions(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    signal_type: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
    _: User = Depends(require_admin),
):
    """Export tenant interaction signals for ML pipelines — never crosses organizations."""
    user, _ = ctx
    q = select(InteractionSignal).where(InteractionSignal.org_id == user.org_id)
    if signal_type:
        q = q.where(InteractionSignal.signal_type == signal_type)
    q = q.order_by(InteractionSignal.created_at.desc()).offset(offset).limit(limit)
    res = await session.execute(q)
    rows = res.scalars().all()
    return [
        {
            "id": str(x.id),
            "signal_type": x.signal_type,
            "payload": x.payload_json,
            "user_id": str(x.user_id) if x.user_id else None,
            "project_id": str(x.project_id) if x.project_id else None,
            "resource_type": x.resource_type,
            "resource_id": x.resource_id,
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in rows
    ]


@router.get("/audit")
async def list_audit(
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _fp = ctx
    q = (
        select(AuditLog)
        .where(AuditLog.org_id == user.org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(q)
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "resource": a.resource,
            "detail": a.detail_json,
            "api_key_fp": a.api_key_fingerprint,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in res.scalars().all()
    ]


@router.post("/dpo-feedback")
async def dpo_feedback(
    body: DPOFeedbackIn,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    await require_brief_in_org(session, body.chosen_brief_id, user.org_id)
    await require_brief_in_org(session, body.rejected_brief_id, user.org_id)
    row = DPOFeedback(
        id=uuid.uuid4(),
        org_id=user.org_id,
        region_id=body.region_id,
        chosen_brief_id=body.chosen_brief_id,
        rejected_brief_id=body.rejected_brief_id,
        annotator_user_id=user.id,
    )
    session.add(row)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="dpo_feedback",
        payload={
            "region_id": str(body.region_id),
            "chosen_brief_id": str(body.chosen_brief_id),
            "rejected_brief_id": str(body.rejected_brief_id),
        },
        user_id=user.id,
        resource_type="dpo_feedback",
        resource_id=str(row.id),
    )
    await write_audit(
        session,
        action="enterprise.dpo",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(body.region_id),
        commit=False,
    )
    await session.commit()
    return {"id": str(row.id)}
