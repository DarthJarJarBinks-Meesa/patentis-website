"""Figure captioning for medtech patents — linked to claim numbers."""

from __future__ import annotations

import re
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.config import get_settings
from patentis_platform.db.models import PatentFigure, PatentRecord
from patentis_platform.graph.cpc_adjacency import active_cpc_prefixes
from patentis_platform.multimodal.claim_segmenter import independent_claims_text
from patentis_platform.synthesis.router import Task, model_router

_FIG = re.compile(r"\b(?:FIG\.?|FIGURE)\s*(\d+[A-Za-z]?)\b", re.IGNORECASE)


async def caption_patent_figures(
    session: AsyncSession,
    patent_id: UUID,
    *,
    force: bool = False,
) -> list[PatentFigure]:
    """Generate captions for figure refs in description/claims; store patent_figures rows."""
    patent = await session.get(PatentRecord, patent_id)
    if not patent:
        return []

    prefixes = active_cpc_prefixes()
    cpc = patent.cpc_subclass or ""
    if prefixes and cpc and not any(cpc.startswith(p) for p in prefixes):
        return []

    if not force:
        existing = await session.execute(
            select(PatentFigure).where(PatentFigure.patent_id == patent_id)
        )
        if existing.scalars().first():
            return list(existing.scalars().all())

    blob = f"{patent.title}\n{patent.abstract}\n{patent.description_text or ''}\n{patent.claims_text or ''}"
    fig_nums = sorted(set(_FIG.findall(blob)))
    if not fig_nums:
        fig_nums = ["1"]

    indep = independent_claims_text(patent.claims_text or "", max_chars=8000)
    system = (
        "You caption medical-device patent figures for R&D whitespace analysis. "
        "Return JSON: {\"figures\": [{\"figure_num\": \"1\", \"caption\": \"...\", "
        "\"claim_refs\": [\"1\", \"2\"]}]}"
    )
    user = (
        f"Patent: {patent.title}\nCPC: {cpc}\n"
        f"Independent claims excerpt:\n{indep}\n\n"
        f"Figure numbers detected: {', '.join(fig_nums)}\n"
        "Describe each figure's device semantics and which claim elements it illustrates."
    )
    data = await model_router.call_json(Task.FIGURE_CAPTIONING, system, user)
    figures_data = data.get("figures", []) if data else []

    rows: list[PatentFigure] = []
    if not figures_data:
        for fn in fig_nums[:12]:
            rows.append(
                PatentFigure(
                    id=uuid.uuid4(),
                    patent_id=patent_id,
                    figure_num=fn,
                    caption=f"Figure {fn} — device illustration for {patent.title[:120]}",
                    claim_refs=["1"],
                )
            )
    else:
        for item in figures_data:
            rows.append(
                PatentFigure(
                    id=uuid.uuid4(),
                    patent_id=patent_id,
                    figure_num=str(item.get("figure_num", "1")),
                    caption=str(item.get("caption", ""))[:4000],
                    claim_refs=item.get("claim_refs") or [],
                )
            )

    for row in rows:
        session.add(row)
    await session.flush()
    return rows


async def caption_active_cpc_patents(session: AsyncSession, limit: int = 20) -> int:
    prefixes = active_cpc_prefixes()
    q = select(PatentRecord).where(PatentRecord.claims_text.isnot(None)).limit(limit * 3)
    res = await session.execute(q)
    n = 0
    for p in res.scalars().all():
        cpc = p.cpc_subclass or ""
        if prefixes and cpc and not any(cpc.startswith(pr) for pr in prefixes):
            continue
        await caption_patent_figures(session, p.id)
        n += 1
        if n >= limit:
            break
    return n
