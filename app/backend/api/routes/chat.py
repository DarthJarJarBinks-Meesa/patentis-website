import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest
from services import session_store, llm, rag
from api.deps import get_groq_key

router = APIRouter()

_SYSTEM_PROMPT = """You are a product development consultant and technical advisor for Patentis.
You are helping the user develop their selected idea while ensuring they do not infringe on existing patents.

Your role:
- Guide step-by-step technical development
- Suggest research labs, academic groups, and experts relevant to the technology
- Recommend tools, frameworks, and methodologies
- Flag any potential patent conflicts as they arise in the development discussion
- Help structure a development roadmap

Be specific, practical, and actionable. Reference the patent landscape context when relevant."""


@router.post("/session/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.selected_idea_index is None:
        raise HTTPException(status_code=400, detail="No idea selected yet")

    selected_idea = session.ideas[session.selected_idea_index]

    # Retrieve relevant context from RAG
    relevant_docs = rag.query_collection(session_id, req.message, n_results=5)
    rag_context = "\n\n".join(d["text"] for d in relevant_docs)

    system_content = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"--- Selected Idea ---\n"
        f"Title: {selected_idea.get('title')}\n"
        f"Description: {selected_idea.get('description')}\n"
        f"Technical Approach: {selected_idea.get('technical_approach')}\n\n"
        f"--- Infringement Check ---\n"
        f"{session.infringement_check or 'Not yet completed.'}\n\n"
        f"--- Relevant Patent/Paper Context ---\n"
        f"{rag_context}"
    )

    history = list(session.messages)
    messages = [{"role": "system", "content": system_content}] + history + [
        {"role": "user", "content": req.message}
    ]

    async def stream_response():
        full_response = ""
        try:
            async for chunk in llm.chat_stream(llm.INSTRUCTION_MODEL, messages, temperature=0.6, groq_api_key=groq_key):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            updated_messages = history + [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": full_response},
            ]
            # Keep last 20 turns to avoid context overflow
            session_store.update_session(session_id, {"messages": updated_messages[-40:]})
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
