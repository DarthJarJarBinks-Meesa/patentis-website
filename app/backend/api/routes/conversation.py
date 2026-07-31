import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from services import session_store, llm, rag
from services.patent_search import search_google_patents, search_epo
from services.paper_search import search_pubmed, search_semantic_scholar
from services.text_utils import strip_think
from api.deps import get_groq_key
from api.routes.ideas import _generate_ideas_stream

router = APIRouter()


class ConversationStartRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _dedup(items):
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.title.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


@router.post("/conversation/start")
async def start_conversation(req: ConversationStartRequest, groq_key: str = Depends(get_groq_key)):
    """
    Orchestrates the full setup pipeline as a single SSE stream:
    keyword extraction → patent/paper search → RAG embedding →
    landscape analysis → idea generation.

    After this completes, use /api/session/{id}/chat for the conversation.
    """
    async def event_stream():
        try:
            # 1. Extract keywords
            yield _sse({"type": "status", "message": "Understanding your domain…"})
            keywords_data = await llm.extract_keywords(req.query, groq_api_key=groq_key)
            keywords: list[str] = keywords_data.get("keywords", req.query.split())
            broad_terms: list[str] = keywords_data.get("broad_terms", [])
            search_terms = keywords + broad_terms

            # 2. Search patents and papers in parallel
            yield _sse({"type": "status", "message": "Searching patents and research papers…"})
            patents_raw, epo_raw, pubmed_raw, ss_raw = await asyncio.gather(
                search_google_patents(search_terms, limit=15),
                search_epo(keywords, limit=8),
                search_pubmed(search_terms, limit=15),
                search_semantic_scholar(search_terms, limit=10),
                return_exceptions=True,
            )

            patents = _dedup([
                p for src in [patents_raw, epo_raw] if isinstance(src, list) for p in src
            ])
            papers = _dedup([
                p for src in [pubmed_raw, ss_raw] if isinstance(src, list) for p in src
            ])

            # 3. Create session and store results
            session = session_store.create_session(req.query)
            session_store.update_session(session.id, {
                "patents": [p.model_dump() for p in patents],
                "papers": [p.model_dump() for p in papers],
                "selected_patent_ids": [p.id for p in patents],
                "selected_paper_ids": [p.id for p in papers],
            })
            yield _sse({
                "type": "search_done",
                "session_id": session.id,
                "patent_count": len(patents),
                "paper_count": len(papers),
            })

            # 4. Embed into RAG
            yield _sse({"type": "status", "message": "Building patent knowledge base…"})
            documents = []
            for patent in patents:
                pat_num = patent.id.replace("gp_", "").replace("epo_", "").upper()
                text = f"PATENT {pat_num}: {patent.title}\n\nAbstract: {patent.abstract}"
                if patent.assignee:
                    text += f"\n\nAssignee: {patent.assignee}"
                documents.append({
                    "id": patent.id,
                    "text": text,
                    "metadata": {"type": "patent", "title": patent.title, "source": patent.source},
                })
            for paper in papers:
                text = f"RESEARCH PAPER: {paper.title}\n\nAbstract: {paper.abstract}"
                if paper.authors:
                    text += f"\n\nAuthors: {', '.join(paper.authors[:5])}"
                documents.append({
                    "id": paper.id,
                    "text": text,
                    "metadata": {"type": "paper", "title": paper.title, "source": paper.source},
                })
            rag.embed_documents(session.id, documents)

            # 5. Stream landscape analysis
            yield _sse({"type": "status", "message": "Mapping the patent landscape…"})

            # Build a truncated context for the LLM — embed full text into RAG above,
            # but cap what we send to the model to stay within payload limits.
            _ABSTRACT_LIMIT = 200   # chars per document sent to LLM
            _CONTEXT_LIMIT  = 6_000   # total chars across all documents
            truncated_parts = [
                d["text"][:_ABSTRACT_LIMIT] + ("…" if len(d["text"]) > _ABSTRACT_LIMIT else "")
                for d in documents
            ]
            context = "\n\n---\n\n".join(truncated_parts)
            if len(context) > _CONTEXT_LIMIT:
                context = context[:_CONTEXT_LIMIT] + "\n\n[Remaining documents omitted for length]"
            analysis_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a patent landscape analyst with deep technical expertise. "
                        "Analyze the provided patents and research papers to map what has been "
                        "patented and identify genuine gaps and opportunities."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Research area: "{req.query}"\n\n'
                        f"Documents:\n{context}\n\n"
                        "Provide a thorough patent landscape analysis:\n\n"
                        "## Covered Territory\n"
                        "List specific technical approaches already patented.\n\n"
                        "## Patent Gaps\n"
                        "Identify specific areas that appear unpatented or underpatented. "
                        "Explain WHY each gap exists.\n\n"
                        "## Research Directions\n"
                        "What technical directions are being explored in papers but not yet patented?\n\n"
                        "## Opportunity Summary\n"
                        "2-3 sentences on the most promising white spaces.\n\n"
                        "## Search Scope\n"
                        "State: 'This landscape covers US patents and EPO/PCT filings. "
                        "It is a research triage tool, not a legal FTO opinion.'"
                    ),
                },
            ]

            yield _sse({"type": "analysis_start"})
            full_analysis = ""
            async for chunk in llm.chat_stream(
                llm.REASONING_MODEL, analysis_messages, temperature=0.3,
                groq_api_key=groq_key, max_tokens=1000,
            ):
                full_analysis += chunk
                yield _sse({"type": "analysis_chunk", "content": chunk})
            clean_analysis = strip_think(full_analysis)
            session_store.update_session(session.id, {"analysis": clean_analysis})
            yield _sse({"type": "analysis_done"})

            # 6. Generate ideas
            yield _sse({"type": "ideas_status", "message": "Finding innovation opportunities…"})
            fresh_session = session_store.get_session(session.id)
            async for event in _generate_ideas_stream(fresh_session, groq_key):
                if "status" in event:
                    yield _sse({"type": "ideas_status", "message": event["status"]})
                elif event.get("done"):
                    yield _sse({"type": "ideas_done", "ideas": event["ideas"]})

            yield _sse({"type": "ready"})

        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
