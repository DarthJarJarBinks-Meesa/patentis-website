"""Audit trail helpers."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    org_id: Optional[uuid.UUID] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    api_key_fingerprint: Optional[str] = None,
    resource: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
    commit: bool = True,
) -> None:
    session.add(
        AuditLog(
            id=uuid.uuid4(),
            org_id=org_id,
            actor_user_id=actor_user_id,
            api_key_fingerprint=api_key_fingerprint,
            action=action,
            resource=resource,
            detail_json=detail,
        )
    )
    if commit:
        await session.commit()
