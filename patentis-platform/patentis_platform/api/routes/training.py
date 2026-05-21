"""Model training ops — masking runs, SFT export (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.masking_config import MaskingConfig
from models.masking_regions import eligible_cpc_subclasses, subgroup_patent_stats
from patentis_platform.api.deps import get_db_session, require_admin
from patentis_platform.db.models import MaskingRunRecord, User

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/masking/eligible-subgroups")
async def masking_eligible(
    dev_mode: bool = Query(False, description="Use relaxed min_region_size for small corpuses"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    cfg = MaskingConfig.development() if dev_mode else MaskingConfig.from_env()
    eligible = await eligible_cpc_subclasses(session, cfg)
    stats = await subgroup_patent_stats(session)
    return {
        "config": {
            "strategy": cfg.strategy.value,
            "n_hidden_min": cfg.n_hidden_min,
            "n_hidden_max": cfg.n_hidden_max,
            "min_region_size": cfg.min_region_size,
            "min_visible_patents": cfg.min_visible_patents,
            "samples_per_region": cfg.samples_per_region,
        },
        "eligible_subgroups": eligible,
        "subgroup_stats": stats,
    }


@router.post("/masking/run")
async def run_masking(
    dev_mode: bool = Query(False),
    cpc_subclass: str | None = Query(None, description="Run one subgroup only"),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_admin),
):
    from models.auto_trainer import run_nightly_masking_job

    cfg = MaskingConfig.development() if dev_mode else MaskingConfig.from_env()
    subgroups = [cpc_subclass] if cpc_subclass else None
    result = await run_nightly_masking_job(cpc_subclasses=subgroups, config=cfg)
    return {"ok": True, "result": result, "triggered_by": str(user.id)}


@router.get("/masking/stats")
async def masking_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    total = await session.scalar(select(func.count()).select_from(MaskingRunRecord))
    accepted = await session.scalar(
        select(func.count()).select_from(MaskingRunRecord).where(MaskingRunRecord.accepted.is_(True))
    )
    return {"total_records": total, "accepted": accepted}
