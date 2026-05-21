"""Per-org LoRA adapter registry — load only for opted-in orgs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import Organization, OrgLoRAAdapter
from patentis_platform.enterprise.org_adapter_store import delete_adapter_artifacts, write_adapter_placeholder


async def get_active_adapter_for_org(session: AsyncSession, org_id: UUID) -> Optional[OrgLoRAAdapter]:
    org = await session.get(Organization, org_id)
    if not org or not org.training_opt_in:
        return None
    res = await session.execute(
        select(OrgLoRAAdapter).where(
            OrgLoRAAdapter.org_id == org_id,
            OrgLoRAAdapter.status == "active",
        )
    )
    return res.scalar_one_or_none()


async def resolve_inference_adapter(session: AsyncSession, org_id: UUID) -> dict[str, Any]:
    """Inference: base Patentis-SFT + optional org LoRA overlay (never cross-tenant)."""
    adapter = await get_active_adapter_for_org(session, org_id)
    return {
        "base_model": "patentis-sft",
        "base_training_data": "public_uspto_masked_only",
        "org_lora_path": adapter.blob_path if adapter else None,
        "org_lora_version": adapter.version if adapter else None,
        "uses_customer_adapter": adapter is not None,
    }


async def ensure_adapter_row(session: AsyncSession, org_id: UUID) -> OrgLoRAAdapter:
    res = await session.execute(select(OrgLoRAAdapter).where(OrgLoRAAdapter.org_id == org_id))
    row = res.scalar_one_or_none()
    if row is None:
        row = OrgLoRAAdapter(
            id=uuid.uuid4(),
            org_id=org_id,
            status="none",
            blob_path=None,
            version=None,
        )
        session.add(row)
        await session.flush()
    return row


async def retire_org_adapter(
    session: AsyncSession,
    org_id: UUID,
    *,
    delete_blobs: bool = False,
) -> Optional[OrgLoRAAdapter]:
    row = await ensure_adapter_row(session, org_id)
    row.status = "retired"
    row.retired_at = datetime.now(timezone.utc)
    if delete_blobs:
        delete_adapter_artifacts(org_id)
        row.blob_path = None
    await session.flush()
    return row


async def activate_adapter_placeholder(
    session: AsyncSession,
    org_id: UUID,
    version: str,
    metadata: dict,
) -> OrgLoRAAdapter:
    org = await session.get(Organization, org_id)
    if not org or not org.training_opt_in:
        raise PermissionError("Org has not opted in to private adapter training")

    blob_path = write_adapter_placeholder(org_id, version, metadata)
    row = await ensure_adapter_row(session, org_id)
    row.status = "active"
    row.blob_path = blob_path
    row.version = version
    row.trained_at = datetime.now(timezone.utc)
    row.retired_at = None
    row.purge_after = None
    await session.flush()
    return row
