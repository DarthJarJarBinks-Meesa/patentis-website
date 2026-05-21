from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import CorpusDocument, OpportunityBrief, Project, User
from patentis_platform.enterprise.audit import write_audit
from patentis_platform.enterprise.interactions import log_interaction
from patentis_platform.multimodal.pipeline import brief_from_pdf_bytes
from patentis_platform.retrieval.embeddings import encode_texts
from patentis_platform.retrieval.hybrid import hybrid_search
from patentis_platform.schemas.api import CorpusUpload, OpportunityBriefOut, ProjectCreate, ProjectOut
from patentis_platform.synthesis.briefs import generate_brief_for_region

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = Project(org_id=user.org_id, name=body.name, query=body.query, vertical=body.vertical)
    session.add(p)
    await session.flush()
    await write_audit(
        session,
        action="project.create",
        org_id=user.org_id,
        actor_user_id=user.id,
        resource=str(p.id),
        commit=False,
    )
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p, from_attributes=True)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    res = await session.execute(select(Project).where(Project.org_id == user.org_id))
    return [ProjectOut.model_validate(p, from_attributes=True) for p in res.scalars().all()]


@router.post("/{project_id}/corpus", response_model=dict)
async def add_corpus(
    project_id: UUID,
    body: CorpusUpload,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    emb = (await asyncio.to_thread(encode_texts, [body.body]))[0]
    doc_id = uuid.uuid4()
    doc = CorpusDocument(
        id=doc_id,
        project_id=project_id,
        title=body.title or "Untitled",
        body=body.body,
        source_type="note",
        embedding=emb.tolist(),
    )
    session.add(doc)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="corpus_added",
        payload={"title": body.title, "chars": len(body.body)},
        user_id=user.id,
        project_id=project_id,
        resource_type="corpus_document",
        resource_id=str(doc_id),
    )
    await session.commit()
    return {"id": str(doc.id)}


@router.post("/{project_id}/corpus/upload-pdf")
async def upload_pdf(
    project_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    raw = await file.read()
    meta = await brief_from_pdf_bytes(raw, region_label=p.query or "upload")
    body_text = meta.get("claims_excerpt") or meta.get("description_excerpt") or ""
    meta["claims_excerpt"] = meta.get("claims_excerpt") or body_text[:8000]
    emb = (await asyncio.to_thread(encode_texts, [body_text[:8000]]))[0] if body_text else None
    doc_id = uuid.uuid4()
    doc = CorpusDocument(
        id=doc_id,
        project_id=project_id,
        title=file.filename or "patent.pdf",
        body=body_text,
        source_type="upload",
        metadata_json=meta,
        embedding=emb.tolist() if emb is not None else None,
    )
    session.add(doc)
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="corpus_pdf_upload",
        payload={"filename": file.filename, "chars": len(body_text)},
        user_id=user.id,
        project_id=project_id,
        resource_type="corpus_document",
        resource_id=str(doc_id),
    )
    await session.commit()
    return {"id": str(doc.id), "metadata": meta}


@router.get("/{project_id}/corpus/search")
async def corpus_search(
    project_id: UUID,
    q: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await hybrid_search(session, project_id, q)


@router.post("/{project_id}/briefs/{region_id}", response_model=OpportunityBriefOut)
async def create_brief(
    project_id: UUID,
    region_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    brief = await generate_brief_for_region(session, project_id, region_id, actor_user_id=user.id)
    return OpportunityBriefOut(
        id=brief.id,
        project_id=brief.project_id,
        region_id=brief.region_id,
        payload=brief.payload,
        citations=brief.citations,
        feasibility_score=brief.feasibility_score,
        withheld_low_feasibility=brief.withheld_low_feasibility,
    )


@router.get("/{project_id}/briefs", response_model=list[OpportunityBriefOut])
async def list_briefs(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    res = await session.execute(
        select(OpportunityBrief).where(OpportunityBrief.project_id == project_id)
    )
    out = []
    for b in res.scalars().all():
        out.append(
            OpportunityBriefOut(
                id=b.id,
                project_id=b.project_id,
                region_id=b.region_id,
                payload=b.payload,
                citations=b.citations,
                feasibility_score=b.feasibility_score,
                withheld_low_feasibility=b.withheld_low_feasibility,
            )
        )
    return out
