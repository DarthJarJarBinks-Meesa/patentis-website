"""Tenant access guards for cross-object lookups."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import OpportunityBrief, Project


async def require_brief_in_org(session: AsyncSession, brief_id: UUID, org_id: UUID) -> OpportunityBrief:
    b = await session.get(OpportunityBrief, brief_id)
    if not b:
        raise HTTPException(status_code=404, detail="Brief not found")
    p = await session.get(Project, b.project_id)
    if not p or p.org_id != org_id:
        raise HTTPException(status_code=403, detail="Brief is outside your organization")
    return b
