import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest
from services import session_store, llm, rag
from services.patent_search import search_google_patents, patent_to_rag_doc
from api.deps import get_groq_key
from api.routes.ideas import _parse_json

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _format_history(history: list[dict], max_messages: int = 6, max_chars: int = 300) -> str:
    if not history:
        return "(no prior messages)"
    trimmed = history[-max_messages:]
    lines = []
    for m in trimmed:
        content = m.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars] + "…"
        lines.append(f"{m.get('role', 'user')}: {content}")
    return "\n".join(lines)


async def _propose_new_concept(session, history: list[dict], user_message: str, groq_key: str) -> dict | None:
    """
    Classifies whether the latest message is asking the assistant to invent a concept that
    isn't already on the table, and if so, drafts it. Returns None (treated as "no") on any
    parse failure so callers fall back to the normal conversational flow.
    """
    ideas_summary = "(none yet)"
    if session.ideas:
        ideas_summary = "\n".join(
            f"- {idea.get('title')}: {idea.get('tagline', '')}" for idea in session.ideas
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You classify turns in a patent-advisory chat and, when needed, draft a candidate "
                "technical concept. Return ONLY valid JSON — no markdown, no preamble."
            ),
        },
        {
            "role": "user",
            "content": (
                f'Patent domain: "{session.query}"\n\n'
                f"Ideas already on the table (already fully described elsewhere, no need to redraft):\n{ideas_summary}\n\n"
                f"Recent conversation:\n{_format_history(history)}\n\n"
                f'Latest engineer message: "{user_message}"\n\n'
                "Is the latest message asking you to invent, design, propose, or synthesize a concept "
                "that is NOT already one of the ideas listed above and wasn't already fully described "
                "earlier in the conversation (e.g. \"design something new\", \"combine X and Y into...\", "
                "\"come up with a concept that...\")? Asking to elaborate on, or check FTO for, an idea "
                "that's already named/described above is NOT a new-concept request — answer false for that.\n\n"
                'If NO, return: {"is_new_concept": false}\n\n'
                "If YES, name exactly ONE concrete, specific concept and return:\n"
                "{\n"
                '  "is_new_concept": true,\n'
                '  "title": "Short name",\n'
                '  "search_keywords": ["4-6 precise technical terms naming this concept\'s specific, '
                'novel components — used to run a live patent search"]\n'
                "}\n\n"
                "Keep this response to just that JSON object — the full concept description comes later. "
                "Every field is short; do not write multi-sentence prose anywhere in this response."
            ),
        },
    ]
    try:
        raw = await llm.chat_complete(llm.INSTRUCTION_MODEL, messages, temperature=0.4, groq_api_key=groq_key, max_tokens=700)
        parsed = _parse_json(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _build_new_concept_messages(title: str, keywords: list[str], patent_context: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are a patent research assistant helping medtech R&D engineers design new "
                "concepts with a clear freedom to operate (FTO). Your output will be handed directly "
                "to patent counsel. EVERY flagged element must cite a specific, verifiable patent "
                "number and the exact relevant claim or passage. Only cite patent numbers that "
                "literally appear in the corpus below — never invent, guess, or recall one from "
                "general knowledge. Use exactly three confidence levels: 'Likely blocked', "
                "'Worth reviewing', 'Appears clear'."
            ),
        },
        {
            "role": "user",
            "content": (
                f'The engineer asked you to design a concept called "{title}", built around: '
                f"{', '.join(keywords)}.\n\n"
                f"Patent corpus (existing session corpus plus a fresh live search run specifically "
                f"for this concept's components):\n{patent_context}\n\n"
                "First, write a concrete 2-3 paragraph description of the concept: what it is, its "
                "key components, and how it works.\n\n"
                "Then produce:\n\n"
                "## FTO Element-by-Element Analysis\n"
                "For each distinct technical element:\n"
                "**Element**: [specific technical element]\n"
                "**Assessment**: Likely blocked | Worth reviewing | Appears clear\n"
                "**Basis**: [Patent number + claim/passage from the corpus above — required for every "
                "non-clear flag. If the corpus has nothing relevant to an element, say so plainly "
                "instead of citing a patent.]\n\n"
                "Do this comparison yourself using the corpus above, now. Never respond with an "
                "instruction for the engineer to 'research this further' or 'conduct a patent search' "
                "— you have the corpus; do that work and report the result.\n\n"
                "## Design-Around Strategies\n"
                "For 'Likely blocked' or 'Worth reviewing' elements, specific modifications to avoid "
                "infringement.\n\n"
                "## Patentability Assessment\n"
                "Which elements appear novel and potentially patentable, with reasoning."
            ),
        },
    ]


async def _stream_new_concept_reply(session_id: str, concept: dict, groq_key: str):
    """
    For a freshly-proposed concept: run a live patent search against its specific
    technical elements (the existing corpus was built for the original query, not for
    components the model is inventing right now), embed the results, then generate the
    concept description and FTO assessment together, grounded only in that combined
    corpus. Yields SSE-shaped events.
    """
    title = concept["title"]
    keywords = [k for k in concept.get("search_keywords", []) if k][:6] or title.split()[:6]

    yield {"status": f"Searching live patent data for “{title}”…"}
    try:
        fresh_patents = await search_google_patents(keywords, limit=10)
    except Exception:
        fresh_patents = []
    if fresh_patents:
        rag.embed_documents(session_id, [patent_to_rag_doc(p) for p in fresh_patents])

    yield {"status": "Checking freedom to operate against the patent corpus…"}
    relevant = rag.query_collection(session_id, f"{title} {' '.join(keywords)}", n_results=12)
    patent_context = "\n\n---\n\n".join(
        d["text"] for d in relevant if d["metadata"].get("type") == "patent"
    )
    if not patent_context:
        patent_context = (
            "No patents in the existing corpus or in a live search for this concept's specific "
            "technical elements were found to be relevant."
        )

    messages = _build_new_concept_messages(title, keywords, patent_context)
    async for chunk in llm.chat_stream(llm.REASONING_MODEL, messages, temperature=0.3, groq_api_key=groq_key):
        yield {"content": chunk}


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
            "- When the engineer describes their own concept or idea, or asks you to go deeper on one of "
            "the identified opportunities ('tell me more about idea N', etc.), IMMEDIATELY assess it for "
            "FTO — cite specific patent NUMBERS and the exact relevant claim or passage for every flag, "
            "use confidence levels ('Likely blocked', 'Worth reviewing', 'Appears clear') per element, "
            "and suggest design-arounds. Never make an unsourced infringement assertion. Only cite patent "
            "numbers that literally appear in the retrieved patent context below — never invent, guess, or "
            "recall a patent number from general knowledge. If no retrieved patent is relevant to an "
            "element, say the corpus doesn't cover it rather than citing one anyway.\n"
            "- After considering all existing patents, evaluate if the concept is patentable using the "
            "retrieved context below. If it is, explain why to the engineer and offer next steps on how "
            "to develop the product. If not, present the design-arounds and allow the engineer to make a "
            "decision. DO NOT end a response telling the engineer to conduct their own thorough patent search, "
            "perform in vitro/in vivo testing, collaborate with regulatory experts, or otherwise go do the "
            "analysis themselves — that is your job. The only acceptable next steps are ones that genuinely "
            "require the engineer's action (e.g. a lab decision only they can make), not restatements of work "
            "you have the context to do right now. Reserve 'Worth reviewing' for elements where you've already "
            "compared the claim language and genuine ambiguity remains, not as a substitute for doing "
            "the comparison.\n"
            "- Help refine and iterate on ideas to maximize novelty and avoid conflicts\n"
            "- Answer technical, regulatory, and commercialization questions\n"
            "- When the retrieved context below includes recent conference papers, proactively surface "
            "specific materials, designs, or methods from them that could improve the concept being "
            "discussed — don't wait to be asked\n"
            "- Be direct, practical, and concise — this is a professional R&D context. Do not ramble.\n"
            "Use bullet points whenever possible.\n\n"
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

    history = list(session.messages)

    async def stream_response():
        full_response = ""
        try:
            concept = None
            if session.analysis:
                concept = await _propose_new_concept(session, history, req.message, groq_key)

            if concept and concept.get("is_new_concept") and concept.get("title"):
                async for event in _stream_new_concept_reply(session_id, concept, groq_key):
                    if "content" in event:
                        full_response += event["content"]
                    yield _sse(event)
            else:
                n_results = 12 if session.analysis else 5
                relevant_docs = rag.query_collection(session_id, req.message, n_results=n_results)
                rag_context = "\n\n".join(d["text"] for d in relevant_docs)
                system_content = _build_system_prompt(session, rag_context)
                messages = [{"role": "system", "content": system_content}] + history + [
                    {"role": "user", "content": req.message}
                ]
                async for chunk in llm.chat_stream(llm.INSTRUCTION_MODEL, messages, temperature=0.6, groq_api_key=groq_key):
                    full_response += chunk
                    yield _sse({"content": chunk})

            updated_messages = history + [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": full_response},
            ]
            # Keep last 20 turns to avoid context overflow
            session_store.update_session(session_id, {"messages": updated_messages[-40:]})
            yield _sse({"done": True})
        except Exception as e:
            yield _sse({"error": str(e)})

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
