"""Enterprise ML training policy, opt-in/out, and org adapter status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_admin, require_org_context
from patentis_platform.db.models import Organization, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.org_adapters import ensure_adapter_row, resolve_inference_adapter
from patentis_platform.enterprise.opt_out import apply_training_opt_out
from patentis_platform.enterprise.training_policy import (
    BASE_SFT_POLICY_TEXT,
    OPT_OUT_POLICY_TEXT,
    ORG_ADAPTER_POLICY_TEXT,
    RETENTION_DAYS_AFTER_OPT_OUT,
)
from patentis_platform.schemas.api import TrainingPolicyOut, TrainingStatusOut

router = APIRouter(prefix="/enterprise/training", tags=["enterprise-training"])


@router.get("/policy", response_model=TrainingPolicyOut)
async def training_policy():
    return TrainingPolicyOut(
        base_sft=BASE_SFT_POLICY_TEXT,
        org_lora=ORG_ADAPTER_POLICY_TEXT,
        opt_out=OPT_OUT_POLICY_TEXT,
        retention_days_after_opt_out=RETENTION_DAYS_AFTER_OPT_OUT,
    )


@router.get("/status", response_model=TrainingStatusOut)
async def training_status(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    org = await session.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    adapter = await ensure_adapter_row(session, user.org_id)
    inference = await resolve_inference_adapter(session, user.org_id)
    return TrainingStatusOut(
        training_opt_in=bool(org.training_opt_in),
        training_opt_out_at=org.training_opt_out_at.isoformat() if org.training_opt_out_at else None,
        training_data_purge_after=(
            org.training_data_purge_after.isoformat() if org.training_data_purge_after else None
        ),
        adapter_status=adapter.status,
        adapter_version=adapter.version,
        adapter_blob_path=adapter.blob_path,
        inference=inference,
    )


@router.post("/opt-out")
async def training_opt_out(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
    _: User = Depends(require_admin),
):
    user, _ = ctx
    result = await apply_training_opt_out(session, user.org_id)
    await write_audit(
        session,
        action="enterprise.training.opt_out",
        org_id=user.org_id,
        actor_user_id=user.id,
        detail=result,
        commit=False,
    )
    await session.commit()
    return result


@router.post("/opt-in")
async def training_opt_in(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
    _: User = Depends(require_admin),
):
    """Enable private LoRA training; does not export data to base Patentis-SFT."""
    user, _ = ctx
    org = await session.get(Organization, user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.training_opt_in = True
    org.training_opt_in_at = datetime.now(timezone.utc)
    org.training_opt_out_at = None
    org.training_data_purge_after = None
    await ensure_adapter_row(session, user.org_id)
    await write_audit(
        session,
        action="enterprise.training.opt_in",
        org_id=user.org_id,
        actor_user_id=user.id,
        commit=False,
    )
    await session.commit()
    return {
        "training_opt_in": True,
        "message": ORG_ADAPTER_POLICY_TEXT,
        "base_model_unchanged": BASE_SFT_POLICY_TEXT,
    }
