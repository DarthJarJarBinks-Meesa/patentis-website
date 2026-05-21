"""Masked patent supervision — hide 5–10 patents per CPC subgroup, predict gaps on the rest."""

from __future__ import annotations

import random
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.masking_config import MaskingConfig, MaskingStrategy
from patentis_platform.db.models import PatentRecord
from patentis_platform.graph.queries import citation_count_for_patent
from patentis_platform.synthesis.router import Task, model_router


def _patent_in_subgroup(patent: PatentRecord, cpc_subclass: str) -> bool:
    if patent.cpc_subclass == cpc_subclass:
        return True
    if patent.cpc_subclass and patent.cpc_subclass.startswith(cpc_subclass):
        return True
    codes = patent.cpc_codes or []
    if isinstance(codes, list):
        return any(
            c == cpc_subclass or (isinstance(c, str) and c.startswith(cpc_subclass))
            for c in codes
        )
    return False


async def fetch_patents_for_subgroup(
    session: AsyncSession,
    cpc_subclass: str,
    *,
    require_claims: bool = True,
) -> list[PatentRecord]:
    """
    All patents in a CPC subgroup: exact subclass, prefix match, or cpc_codes membership.
    Ordered by filing_date ascending (temporal masking hides the most recent).
    """
    q = select(PatentRecord).where(
        or_(
            PatentRecord.cpc_subclass == cpc_subclass,
            PatentRecord.cpc_subclass.like(f"{cpc_subclass}%"),
        )
    )
    if require_claims:
        q = q.where(PatentRecord.claims_text.isnot(None))
    q = q.order_by(PatentRecord.filing_date.asc().nulls_first())
    res = await session.execute(q)
    by_id: dict[UUID, PatentRecord] = {p.id: p for p in res.scalars().all()}

    if require_claims:
        extra_res = await session.execute(
            select(PatentRecord)
            .where(PatentRecord.claims_text.isnot(None))
            .where(PatentRecord.cpc_codes.isnot(None))
        )
    else:
        extra_res = await session.execute(
            select(PatentRecord).where(PatentRecord.cpc_codes.isnot(None))
        )
    for p in extra_res.scalars().all():
        if _patent_in_subgroup(p, cpc_subclass):
            by_id[p.id] = p

    return sorted(
        by_id.values(),
        key=lambda p: p.filing_date or date.min,
    )


async def count_patents_for_subgroup(session: AsyncSession, cpc_subclass: str) -> int:
    return len(await fetch_patents_for_subgroup(session, cpc_subclass, require_claims=False))


def _format_visible_corpus(patents: list[PatentRecord], cpc_subclass: str) -> str:
    blocks = []
    for p in patents:
        claims_preview = (p.claims_text or "")[:800]
        blocks.append(
            f"Patent {p.external_id} ({p.filing_date}) — {p.title}\n"
            f"Assignee: {p.assignee or 'unknown'}\n"
            f"Claims (excerpt): {claims_preview}"
        )
    corpus_text = "\n\n---\n\n".join(blocks)
    return (
        f"You are analyzing the patent landscape for CPC region {cpc_subclass}.\n"
        f"The following {len(patents)} patents exist in this space.\n\n"
        f"{corpus_text}\n\n"
        f"Identify genuine innovation gaps — areas where no patent has staked a claim. "
        f"Output a JSON OpportunityBrief with fields: gap_description, why_it_exists, "
        f"predicted_claim_space, suggested_directions (list), confidence, citations."
    )


async def build_masked_record(
    session: AsyncSession,
    cpc_subclass: str,
    config: MaskingConfig,
) -> dict[str, Any] | None:
    """
    Fetch patents in CPC subgroup, hide 5–10, build one SFT training record from visible corpus.
    Returns None if the subgroup is too small to mask safely.
    """
    patents = await fetch_patents_for_subgroup(session, cpc_subclass, require_claims=True)
    if len(patents) < config.min_region_size:
        return None

    n_hidden = random.randint(
        config.n_hidden_min,
        min(config.n_hidden_max, len(patents) - config.min_visible_patents),
    )
    if n_hidden < config.n_hidden_min:
        return None

    if config.strategy == MaskingStrategy.TEMPORAL:
        visible = patents[:-n_hidden]
        hidden = patents[-n_hidden:]
    elif config.strategy == MaskingStrategy.CITATION_SPARSE:
        counts: list[tuple[PatentRecord, int]] = []
        for p in patents:
            cnt = await citation_count_for_patent(session, p.id)
            counts.append((p, cnt))
        counts.sort(key=lambda x: x[1])
        hidden = [p for p, _ in counts[:n_hidden]]
        hidden_ids = {p.id for p in hidden}
        visible = [p for p in patents if p.id not in hidden_ids]
    else:
        hidden = random.sample(patents, n_hidden)
        hidden_ids = {p.id for p in hidden}
        visible = [p for p in patents if p.id not in hidden_ids]

    if len(visible) < config.min_visible_patents:
        return None

    prompt = _format_visible_corpus(visible, cpc_subclass)
    system = "You are Patentis. Output a single JSON whitespace opportunity brief."
    brief_json = await model_router.call_json(Task.WHITESPACE_BRIEF, system, prompt)

    return {
        "cpc_subclass": cpc_subclass,
        "strategy": config.strategy.value,
        "n_visible": len(visible),
        "n_hidden": len(hidden),
        "visible_patent_ids": [str(p.id) for p in visible],
        "hidden_patent_ids": [str(p.id) for p in hidden],
        "hidden_patent_claims": [p.claims_text or "" for p in hidden],
        "prompt": prompt,
        "completion": brief_json,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
