from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.api.deps import get_db_session, require_org_context
from patentis_platform.db.models import Organization, Project, User
from patentis_platform.enterprise.interactions import format_org_profile_for_prompt, log_interaction
from patentis_platform.retrieval.hybrid import hybrid_search
from patentis_platform.synthesis.router import chat_json

router = APIRouter(prefix="/analyst", tags=["analyst"])


class AnalystChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/{project_id}/chat")
async def analyst_chat(
    project_id: UUID,
    body: AnalystChatIn,
    session: AsyncSession = Depends(get_db_session),
    ctx: tuple[User, str | None] = Depends(require_org_context),
):
    user, _ = ctx
    p = await session.get(Project, project_id)
    if not p or p.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    org = await session.get(Organization, p.org_id)
    profile = org.profile_json if org and org.profile_json else {}
    company_ctx = format_org_profile_for_prompt(profile)
    hits = await hybrid_search(session, project_id, body.message, top_k=6)
    context = "\n\n".join(f"[{h['title']}] {h['snippet']}" for h in hits)
    parsed = await chat_json(
        system=(
            "You are Patentis Analyst. Answer using only the provided corpus snippets and the "
            "company capability profile as framing — do not invent facts. If insufficient evidence, say so. "
            "Not legal advice."
        ),
        user=(
            f"Company capability profile:\n{company_ctx}\n\n"
            f"Question: {body.message}\n\nCorpus:\n{context}\n\n"
            "Reply as JSON with key answer (string)."
        ),
    )
    answer = parsed.get("answer") if parsed else (
        "Configure OPENAI_API_KEY for live answers. Retrieved context:\n" + context[:1500]
    )
    await log_interaction(
        session,
        org_id=user.org_id,
        signal_type="analyst_chat",
        payload={
            "question": body.message[:4000],
            "answer_preview": str(answer)[:2000],
            "source_count": len(hits),
        },
        user_id=user.id,
        project_id=project_id,
    )
    await session.commit()
    return {"answer": answer, "sources": hits}
