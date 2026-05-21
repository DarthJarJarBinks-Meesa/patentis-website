"""Tenant-scoped interaction logs for personalization datasets and future fine-tunes."""

from __future__ import annotations

import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from patentis_platform.db.models import InteractionSignal, Organization


async def log_interaction(
    session: AsyncSession,
    *,
    org_id: UUID,
    signal_type: str,
    payload: dict[str, Any],
    user_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> InteractionSignal | None:
    org_res = await session.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalar_one_or_none()
    if org is not None and not org.training_opt_in:
        return None
    row = InteractionSignal(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        signal_type=signal_type,
        payload_json=payload,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    session.add(row)
    return row


def format_org_profile_for_prompt(profile: dict[str, Any] | None) -> str:
    """Turn stored org profile JSON into LLM context (tenant-private)."""
    if not profile:
        return "(No company capability profile configured yet.)"
    parts: list[str] = []
    cap = profile.get("core_capabilities")
    if isinstance(cap, list) and cap:
        parts.append("Core capabilities / strengths: " + "; ".join(str(x) for x in cap[:20]))
    avoid = profile.get("avoid_or_out_of_scope")
    if isinstance(avoid, list) and avoid:
        parts.append("Out of scope / avoid: " + "; ".join(str(x) for x in avoid[:15]))
    focus = profile.get("strategic_focus")
    if isinstance(focus, str) and focus.strip():
        parts.append("Strategic focus: " + focus.strip()[:2000])
    rd = profile.get("current_rd_directions")
    if isinstance(rd, list) and rd:
        parts.append("Current R&D / product directions (from customer): " + "; ".join(str(x) for x in rd[:15]))
    notes = profile.get("additional_context")
    if isinstance(notes, str) and notes.strip():
        parts.append("Additional context: " + notes.strip()[:3000])
    if not parts:
        return "(Company profile exists but has no structured fields filled.)"
    return "\n".join(parts)
