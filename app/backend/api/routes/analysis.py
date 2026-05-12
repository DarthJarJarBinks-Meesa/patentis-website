import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from services import session_store, rag, llm
from models.schemas import Patent, Paper
from api.deps import get_groq_key

router = APIRouter()


@router.post("/session/{session_id}/analyze")
async def analyze(session_id: str, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.selected_patent_ids and not session.selected_paper_ids:
        raise HTTPException(status_code=400, detail="No documents selected")

    selected_patents = [
        Patent(**p) if isinstance(p, dict) else p
        for p in session.patents
        if (p["id"] if isinstance(p, dict) else p.id) in session.selected_patent_ids
    ]
    selected_papers = [
        Paper(**p) if isinstance(p, dict) else p
        for p in session.papers
        if (p["id"] if isinstance(p, dict) else p.id) in session.selected_paper_ids
    ]

    documents = []
    for patent in selected_patents:
        text = f"PATENT: {patent.title}\n\nAbstract: {patent.abstract}"
        if patent.assignee:
            text += f"\n\nAssignee: {patent.assignee}"
        documents.append(
            {
                "id": patent.id,
                "text": text,
                "metadata": {"type": "patent", "title": patent.title, "source": patent.source},
            }
        )

    for paper in selected_papers:
        text = f"RESEARCH PAPER: {paper.title}\n\nAbstract: {paper.abstract}"
        if paper.authors:
            text += f"\n\nAuthors: {', '.join(paper.authors[:5])}"
        documents.append(
            {
                "id": paper.id,
                "text": text,
                "metadata": {"type": "paper", "title": paper.title, "source": paper.source},
            }
        )

    rag.embed_documents(session_id, documents)
    all_docs = rag.get_all_documents(session_id)
    context = "\n\n---\n\n".join(d["text"] for d in all_docs)

    messages = [
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
                f'Research area: "{session.query}"\n\n'
                f"Documents:\n{context}\n\n"
                "Provide a thorough patent landscape analysis with these sections:\n\n"
                "## Covered Territory\n"
                "List specific technical approaches and methods that are already patented. "
                "Be precise about what claims are covered.\n\n"
                "## Patent Gaps\n"
                "Identify specific technical areas that appear unpatented or underpatented. "
                "Explain WHY each gap exists and what makes it potentially patentable.\n\n"
                "## Research Directions\n"
                "Based on the academic papers, what technical directions are being explored "
                "that have not yet been patented?\n\n"
                "## Opportunity Summary\n"
                "2-3 sentences identifying the most promising white spaces for new patents."
            ),
        },
    ]

    async def stream_analysis():
        full_response = ""
        try:
            async for chunk in llm.chat_stream(llm.REASONING_MODEL, messages, temperature=0.3, groq_api_key=groq_key):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            session_store.update_session(session_id, {"analysis": full_response})
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_analysis(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
