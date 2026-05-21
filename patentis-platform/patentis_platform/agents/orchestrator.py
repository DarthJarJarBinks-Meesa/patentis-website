"""Composable workflow agents."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import OrgRegionScore, PatentRecord, Project, TechnologyRegion
from patentis_platform.feasibility.pubmed import feasibility_from_keywords
from patentis_platform.graph.build import ensure_region_for_subclass, rebuild_region_counts
from patentis_platform.ingestion.patentsview import (
    parse_filing_date,
    query_patents_by_cpc_subclass,
    row_to_assignee,
    row_to_cpc_subclass,
    row_to_external_id,
    row_to_title,
)
from patentis_platform.retrieval.embeddings import encode_texts
from patentis_platform.retrieval.hybrid import hybrid_search
from patentis_platform.scoring.models_ml import apply_saved_models
from patentis_platform.scoring.tenant_landscape import effective_composite, load_org_overlays
from patentis_platform.synthesis.briefs import generate_brief_for_region


async def agent_whitespace_scan(
    session: AsyncSession,
    vertical: str,
    top_n: int = 10,
    org_id: UUID | None = None,
) -> list[dict[str, Any]]:
    res = await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
    rows = list(res.scalars().all())
    overlays: dict[UUID, OrgRegionScore] = {}
    if org_id:
        overlays = await load_org_overlays(session, org_id)

    if overlays:
        rows.sort(key=lambda r: effective_composite(r, overlays.get(r.id)), reverse=True)
    else:
        rows.sort(
            key=lambda r: r.composite_whitespace_score if r.composite_whitespace_score is not None else -1.0,
            reverse=True,
        )
    rows = rows[:top_n]
    return [
        {
            "region_id": str(r.id),
            "cpc": r.cpc_subclass,
            "composite": (
                overlays[r.id].composite_whitespace_score
                if r.id in overlays and overlays[r.id].composite_whitespace_score is not None
                else r.composite_whitespace_score
            ),
            "scarcity": r.scarcity_score,
            "momentum": r.momentum_score,
            "tenant_overlay": r.id in overlays,
        }
        for r in rows
    ]


async def agent_feasibility_pass(session: AsyncSession, region_id: UUID) -> dict[str, Any]:
    reg = await session.get(TechnologyRegion, region_id)
    if not reg:
        return {"error": "region not found"}
    kw = [reg.cpc_subclass, "medical device", "implant", "therapy"]
    feas = await feasibility_from_keywords(kw)
    return feas


async def agent_invention_brief(
    session: AsyncSession, project_id: UUID, region_id: UUID, actor_user_id: UUID | None = None
) -> dict[str, Any]:
    ctx_docs = await hybrid_search(session, project_id, "patent whitespace opportunity", top_k=5)
    extra = "\n".join(x["snippet"] for x in ctx_docs)
    brief = await generate_brief_for_region(
        session, project_id, region_id, extra_context=extra, actor_user_id=actor_user_id
    )
    return {
        "brief_id": str(brief.id),
        "withheld": brief.withheld_low_feasibility,
        "feasibility": brief.feasibility_score,
        "payload": brief.payload,
        "citations": brief.citations,
    }


async def agent_risk_sketch(
    session: AsyncSession, region_id: UUID, idea_summary: str
) -> dict[str, Any]:
    reg = await session.get(TechnologyRegion, region_id)
    if not reg:
        return {"error": "region not found"}
    p_res = await session.execute(
        select(PatentRecord).where(PatentRecord.cpc_subclass == reg.cpc_subclass).limit(20)
    )
    patents = list(p_res.scalars().all())
    overlap_hits = []
    idea_l = idea_summary.lower()
    for p in patents:
        blob = f"{p.title} {p.abstract}".lower()
        if any(tok in blob for tok in idea_l.split() if len(tok) > 4):
            overlap_hits.append({"patent": p.external_id, "title": p.title})
    return {
        "disclaimer": "High-level overlap sketch only — not FTO or legal clearance.",
        "potential_overlaps": overlap_hits[:8],
    }


async def run_full_pipeline(
    session: AsyncSession,
    project_id: UUID,
    vertical: str,
    idea_summary: str,
    actor_user_id: UUID | None = None,
) -> dict[str, Any]:
    p = await session.get(Project, project_id)
    if not p:
        return {"error": "project not found"}
    scan = await agent_whitespace_scan(session, vertical, top_n=3, org_id=p.org_id)
    if not scan:
        return {"error": "no regions — seed and train models first"}
    rid = UUID(scan[0]["region_id"])
    feas = await agent_feasibility_pass(session, rid)
    brief = await agent_invention_brief(session, project_id, rid, actor_user_id=actor_user_id)
    risk = await agent_risk_sketch(session, rid, idea_summary)
    return {"scan_top": scan, "feasibility": feas, "brief": brief, "risk_sketch": risk}


async def refresh_scores_if_models(session: AsyncSession, vertical: str) -> int:
    res = await session.execute(select(TechnologyRegion).where(TechnologyRegion.vertical == vertical))
    regions = list(res.scalars().all())
    scores = apply_saved_models(regions)
    if not scores:
        return 0
    for r, s in zip(regions, scores):
        r.isolation_forest_score = s["if"]
        r.rf_opportunity_score = s["rf"]
        r.composite_whitespace_score = s["composite"]
    await session.commit()
    return len(scores)


async def ingest_cpc_sample(
    session: AsyncSession, prefix: str, limit: int = 40, vertical: str = "medtech"
) -> int:
    """Fetch sample patents for a CPC prefix and persist (best-effort)."""
    rows = await query_patents_by_cpc_subclass(prefix, per_page=limit)

    n = 0
    bodies: list[str] = []
    pending: list[tuple] = []
    for row in rows:
        eid = row_to_external_id(row)
        title = row_to_title(row)
        if not eid or not title:
            continue
        existing = await session.execute(select(PatentRecord).where(PatentRecord.external_id == eid))
        if existing.scalar_one_or_none():
            continue
        cpc = row_to_cpc_subclass(row, prefix)
        abstract = str(row.get("patent_abstract") or "")
        bodies.append(f"{title}\n{abstract}")
        pending.append((eid, title, abstract, cpc, row))
        n += 1
    if not bodies:
        await ensure_region_for_subclass(session, prefix[:4], vertical=vertical)
        await session.commit()
        return 0
    embs = await asyncio.to_thread(encode_texts, bodies)
    for i, (eid, title, abstract, cpc, row) in enumerate(pending):
        session.add(
            PatentRecord(
                id=uuid.uuid4(),
                external_id=eid,
                title=title,
                abstract=abstract[:4000],
                cpc_subclass=cpc,
                assignee=row_to_assignee(row),
                filing_date=parse_filing_date(row),
                source="patentsview",
                url=f"https://patents.google.com/patent/{eid}/en",
                embedding=embs[i].tolist(),
            )
        )
    await ensure_region_for_subclass(session, prefix[:4], vertical=vertical)
    await rebuild_region_counts(session, vertical=vertical)
    await session.commit()
    return n
