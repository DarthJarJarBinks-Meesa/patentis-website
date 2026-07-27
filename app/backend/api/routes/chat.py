import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest
from services import session_store, llm, rag
from api.deps import get_groq_key

router = APIRouter()

def _build_system_prompt(session, rag_context: str) -> str:
    """Build a system prompt appropriate for the session's current state."""

    if session.analysis:
        # Conversational mode — full landscape context is available
        ideas_text = ""
        if session.ideas:
            ideas_text = "\n\n--- Innovation Opportunities Identified ---\n"
            for i, idea in enumerate(session.ideas):
                ideas_text += (
                    f"\n{i + 1}. {idea.get('title')}\n"
                    f"   {idea.get('tagline', '')}\n"
                    f"   Key innovation: {idea.get('key_innovation', '')}\n"
                    f"   Why unpatented: {idea.get('why_unpatented', '')}\n"
                )

        selected_note = ""
        if session.selected_idea_index is not None:
            sel = session.ideas[session.selected_idea_index]
            selected_note = (
                f"\n\n--- Currently Exploring ---\n"
                f"{sel.get('title')}: {sel.get('description', '')}"
            )
        elif session.user_idea:
            selected_note = (
                f"\n\n--- Engineer's Idea Under Development ---\n"
                f"{session.user_idea.get('title')}: {session.user_idea.get('description', '')}"
            )

        return (
            f"You are an R&D patent advisor helping engineers explore innovation opportunities in {session.query}.\n\n"
            "Your role:\n"
            "- Discuss the patent landscape conversationally and help engineers navigate opportunities\n"
            "- When the engineer describes their own concept or idea, IMMEDIATELY assess it for FTO — "
            "cite specific patent NUMBERS and the exact relevant claim or passage for every flag, "
            "use confidence levels ('Likely blocked', 'Worth reviewing', 'Appears clear') per element, "
            "and suggest design-arounds. Never make an unsourced infringement assertion.\n"
            "- Help refine and iterate on ideas to maximize novelty and avoid conflicts\n"
            "- Answer technical, regulatory, and commercialization questions\n"
            "- Be direct and practical — this is a professional R&D context\n\n"
            "ALWAYS follow these output rules for every response:\n\n"
            "1. SOURCES: Every factual claim must link to a real source. Format as markdown: [Title](URL). "
            "If referencing an academic paper, include the DOI link AND a Sci-Hub link: "
            "[PDF via Sci-Hub](https://sci-hub.se/DOI). Only include Sci-Hub links for real papers with known DOIs.\n\n"
            "2. MARKET DATA: When discussing market size, costs, adoption, or competitive landscape, "
            "include real figures with sources. Example: 'FTO opinions typically cost $10,000-$50,000 "
            "([LeanLaw](https://www.leanlaw.co/blog/how-to-structure-freedom-to-operate-fto-opinions-capping-costs-while-defining-clear-search-scope/))'. "
            "Cite market research reports when available.\n\n"
            "3. VENDORS: When discussing components, materials, manufacturing, or tooling relevant to a "
            "device concept, name specific real vendors. For medtech: implant manufacturers (Zimmer Biomet, "
            "Stryker, DePuy Synthes), materials suppliers (Enovis, Carpenter Technology for titanium alloys, "
            "Solvay for PEEK), CROs, testing labs (Nelson Labs, Toxikon), sterilization vendors (Sterigenics), "
            "and contract manufacturers (Resonetics, Accellent/Viant). Link to vendor websites where possible.\n\n"
            "4. FURTHER READING: End every substantive response with a 'Further Reading' section listing "
            "2-3 relevant articles, papers, or reports with working links.\n\n"
            f"--- Patent Landscape Analysis ---\n{session.analysis[:3000]}"
            f"{ideas_text}"
            f"{selected_note}\n\n"
            f"--- Relevant Patent/Paper Context (retrieved for this message) ---\n{rag_context}"
        )

    # Legacy step-by-step mode
    selected_idea = None
    if session.selected_idea_index is not None:
        selected_idea = session.ideas[session.selected_idea_index]
    elif session.user_idea:
        selected_idea = session.user_idea

    return (
        "You are a product development consultant and technical advisor for Patentis. "
        "You are helping the user develop their selected idea while ensuring they do not infringe on existing patents.\n\n"
        "Your role:\n"
        "- Guide step-by-step technical development\n"
        "- Suggest research labs, academic groups, and experts relevant to the technology\n"
        "- Flag any potential patent conflicts as they arise\n"
        "- Help structure a development roadmap\n\n"
        "ALWAYS follow these output rules for every response:\n\n"
        "1. SOURCES: Every factual claim must link to a real source. Format as markdown: [Title](URL). "
        "If referencing an academic paper, include the DOI link AND a Sci-Hub link: "
        "[PDF via Sci-Hub](https://sci-hub.se/DOI). Only include Sci-Hub links for real papers with known DOIs.\n\n"
        "2. MARKET DATA: When discussing market size, costs, adoption, or competitive landscape, "
        "include real figures with sources.\n\n"
        "3. VENDORS: When discussing components, materials, manufacturing, or tooling, name specific real vendors "
        "with links. For medtech: implant manufacturers (Zimmer Biomet, Stryker, DePuy Synthes), "
        "materials suppliers (Carpenter Technology for titanium alloys, Solvay for PEEK), "
        "testing labs (Nelson Labs, Toxikon), sterilization vendors (Sterigenics), "
        "and contract manufacturers (Resonetics, Viant). Link to vendor websites where possible.\n\n"
        "4. FURTHER READING: End every substantive response with a 'Further Reading' section listing "
        "2-3 relevant articles or papers with working links.\n\n"
        f"--- Selected Idea ---\n"
        f"Title: {selected_idea.get('title') if selected_idea else 'Not specified'}\n"
        f"Description: {selected_idea.get('description', '') if selected_idea else ''}\n\n"
        f"--- Infringement Check ---\n{session.infringement_check or 'Not yet completed.'}\n\n"
        f"--- Relevant Patent/Paper Context ---\n{rag_context}"
    )


@router.post("/session/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    # Allow conversation-mode chat (no idea required when analysis exists)
    if not session.analysis and session.selected_idea_index is None and session.user_idea is None:
        raise HTTPException(status_code=400, detail="No idea selected or submitted yet")

    # Broader RAG context in conversation mode
    n_results = 12 if session.analysis else 5
    relevant_docs = rag.query_collection(session_id, req.message, n_results=n_results)
    rag_context = "\n\n".join(d["text"] for d in relevant_docs)

    system_content = _build_system_prompt(session, rag_context)

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
