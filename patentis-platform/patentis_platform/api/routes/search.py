"""v1-inspired parallel search — persisted to Postgres projects (not in-memory sessions)."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import Project, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.ingestion.patent_search import PatentHit, search_epo, search_google_patents
from patentis_platform.ingestion.paper_search import PaperHit
from patentis_platform.ingestion.pubmed_sync import search_all_literature
from patentis_platform.ingestion.search_persist import persist_search_hits
from patentis_platform.multimodal.gap_identification import identify_innovation_gaps
from patentis_platform.schemas.search import (
    MultimodalGapRequest,
    MultimodalGapResponse,
    PaperHitOut,
    PatentHitOut,
    ProjectSearchRequest,
    ProjectSearchResponse,
)
from patentis_platform.synthesis.keywords import extract_search_keywords

router = APIRouter(tags=["search"])


@router.post("/projects/{project_id}/search", response_model=ProjectSearchResponse)
async def project_search(
    project_id: UUID,
    body: ProjectSearchRequest,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    """
    Parallel patent + literature search (patentisv1 flow), stored on the project for RAG and gap ID.
    Sources: Google Patents, optional EPO OPS, PubMed.
    """
    user, _ = ctx
    proj = await session.get(Project, project_id)
    if not proj or proj.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")

    keywords_data = await extract_search_keywords(body.query)
    keywords: list[str] = keywords_data.get("keywords", body.query.split())
    broad: list[str] = keywords_data.get("broad_terms", [])
    search_terms = keywords + broad

    patents_results, epo_results, literature_results = await asyncio.gather(
        search_google_patents(search_terms, limit=15),
        search_epo(keywords, limit=8),
        search_all_literature(search_terms, limit_per_source=10),
        return_exceptions=True,
    )

    patents: list[PatentHit] = []
    for result in (patents_results, epo_results):
        if isinstance(result, list):
            patents.extend(result)

    papers: list[PaperHit] = literature_results if isinstance(literature_results, list) else []

    proj.query = body.query
    counts = await persist_search_hits(session, project_id, patents, papers)

    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="project_search",
        payload={
            "query": body.query[:500],
            "keywords": keywords_data,
            "patent_hits": len(patents),
            "paper_hits": len(papers),
        },
        user_id=user.id,
        project_id=project_id,
    )
    await write_audit(
        session,
        action="search.project",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(project_id),
        detail=counts,
        commit=False,
    )
    await session.commit()

    return ProjectSearchResponse(
        project_id=str(project_id),
        keywords=keywords_data,
        patents=[PatentHitOut.model_validate(p.__dict__) for p in patents],
        papers=[
            PaperHitOut(
                external_id=p.external_id,
                title=p.title,
                abstract=p.abstract,
                url=p.url,
                source=p.source,
                authors=p.authors or [],
            )
            for p in papers
        ],
        persisted=counts,
    )


@router.post(
    "/projects/{project_id}/regions/{region_id}/identify-gaps",
    response_model=MultimodalGapResponse,
)
async def multimodal_identify_gaps(
    project_id: UUID,
    region_id: UUID,
    body: MultimodalGapRequest,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    """
    Multimodal whitespace gap identification (v2 differentiator).
    Run project search first so corpus has patents/papers; upload PDFs for claims_text modality.
    """
    user, _ = ctx
    try:
        out = await identify_innovation_gaps(
            session,
            project_id,
            region_id,
            org_id=user.org_id,
            idea_hint=body.idea_hint,
            use_vision=body.use_vision,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="multimodal_gap_identification",
        payload={
            "region_id": str(region_id),
            "idea_hint": body.idea_hint[:200],
            "modalities": out.get("modality_sources", []),
            "gap_count": len(out.get("gaps_analysis", {}).get("gaps", [])),
        },
        user_id=user.id,
        project_id=project_id,
    )
    await write_audit(
        session,
        action="gaps.multimodal",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=f"{project_id}:{region_id}",
        commit=False,
    )
    await session.commit()
    return MultimodalGapResponse(**out)
