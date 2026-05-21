"""Training opt-out: retire adapter + schedule log/artifact purge within 30 days."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import InteractionSignal, Organization
from patentis_platform.enterprise.org_adapters import ensure_adapter_row, retire_org_adapter
from patentis_platform.enterprise.training_policy import RETENTION_DAYS_AFTER_OPT_OUT


async def apply_training_opt_out(session: AsyncSession, org_id: UUID) -> dict[str, Any]:
    """
    Immediate: opt-out flag, retire adapter metadata.
    Within 30 days: worker purges interaction_signals + blob artifacts (see purge_due_org_training_data).
    """
    org = await session.get(Organization, org_id)
    if not org:
        raise ValueError("Organization not found")

    now = datetime.now(timezone.utc)
    purge_after = now + timedelta(days=RETENTION_DAYS_AFTER_OPT_OUT)

    org.training_opt_in = False
    org.training_opt_out_at = now
    org.training_data_purge_after = purge_after

    adapter = await retire_org_adapter(session, org_id, delete_blobs=False)
    if adapter:
        adapter.purge_after = purge_after

    return {
        "training_opt_in": False,
        "adapter_status": adapter.status if adapter else "none",
        "purge_scheduled_after": purge_after.isoformat(),
        "retention_days": RETENTION_DAYS_AFTER_OPT_OUT,
        "immediate_effects": [
            "Private LoRA adapter retired (no longer loaded at inference)",
            "Interaction logging disabled",
            "Interaction logs and adapter files deleted on or before purge date",
        ],
    }


async def purge_due_org_training_data(session: AsyncSession) -> dict[str, int]:
    """Delete interaction logs and adapter blobs for orgs past purge deadline."""
    from patentis_platform.db.models import Organization as Org
    from patentis_platform.enterprise.org_adapter_store import delete_adapter_artifacts

    now = datetime.now(timezone.utc)
    from sqlalchemy import select

    res = await session.execute(
        select(Org).where(
            Org.training_data_purge_after.isnot(None),
            Org.training_data_purge_after <= now,
        )
    )
    orgs = list(res.scalars().all())
    logs_deleted = 0
    adapters_purged = 0

    for org in orgs:
        r = await session.execute(delete(InteractionSignal).where(InteractionSignal.org_id == org.id))
        logs_deleted += r.rowcount or 0
        if delete_adapter_artifacts(org.id):
            adapters_purged += 1
        await retire_org_adapter(session, org.id, delete_blobs=True)
        adapter_row = await ensure_adapter_row(session, org.id)
        adapter_row.purge_after = None
        org.training_data_purge_after = None
        org.training_opt_out_at = None

    await session.flush()
    return {"orgs_purged": len(orgs), "logs_deleted": logs_deleted, "adapters_purged": adapters_purged}
