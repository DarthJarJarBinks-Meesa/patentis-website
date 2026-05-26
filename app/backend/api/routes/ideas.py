import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from services import session_store, llm, rag
from services.paper_search import search_pubmed
from services.text_utils import strip_think
from models.schemas import SelectIdeaRequest, EvaluateIdeaRequest
from api.deps import get_groq_key

router = APIRouter()


def _parse_json(text: str) -> any:
    text = strip_think(text)
    if not text:
        raise json.JSONDecodeError("Empty response after stripping think blocks", "", 0)
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract outermost [...] or {...} — handles preamble/postamble text
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("Could not extract JSON", text, 0)


@router.post("/session/{session_id}/generate-ideas")
async def generate_ideas(session_id: str, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.analysis:
        raise HTTPException(status_code=400, detail="Run analysis first")

    async def event_stream():
        import traceback
        try:
            async for event in _generate_ideas_stream(session, groq_key):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'error': f'{type(e).__name__}: {e}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _generate_ideas_stream(session, groq_key: str = ""):
    yield {"status": "Generating candidate ideas…"}

    # Stage 1: Generate 7 candidate ideas from patent gap analysis
    candidate_messages = [
        {
            "role": "system",
            "content": (
                "You are an innovation consultant specializing in patent strategy. "
                "Generate novel, technically sound ideas that fill identified gaps in the patent landscape. "
                "Return ONLY valid JSON — no markdown, no preamble."
            ),
        },
        {
            "role": "user",
            "content": (
                f'Patent landscape analysis for "{session.query}":\n\n'
                f"{session.analysis[:2500]}\n\n"
                "Generate exactly 7 novel product/technology ideas that:\n"
                "1. Specifically fill the identified patent gaps\n"
                "2. Are technically feasible\n"
                "3. Have clear commercial or societal potential\n"
                "4. Do NOT replicate any patented approach described above\n\n"
                "Return a JSON array:\n"
                "[\n"
                "  {\n"
                '    "title": "Short descriptive name",\n'
                '    "tagline": "One sentence value proposition",\n'
                '    "description": "2-3 paragraph technical description",\n'
                '    "key_innovation": "The specific novel element that makes this patentable",\n'
                '    "target_market": "Who needs this and why",\n'
                '    "technical_approach": "Step-by-step explanation of how it works",\n'
                '    "why_unpatented": "Specific reason this approach is not covered by existing patents",\n'
                '    "research_keywords": ["keyword1", "keyword2", "keyword3"]\n'
                "  }\n"
                "]\n\n"
                'Include 3-4 precise technical terms in "research_keywords" '
                "that would find relevant research papers validating the scientific basis of the idea."
            ),
        },
    ]

    raw = await llm.chat_complete(llm.REASONING_MODEL, candidate_messages, temperature=0.85, groq_api_key=groq_key, max_tokens=3000)
    try:
        candidates = _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("Model returned malformed JSON for candidates")

    yield {"status": "Searching research literature…"}

    # Stage 2: Search PubMed with combined keywords from all candidates
    all_keywords: list[str] = []
    for idea in candidates:
        all_keywords.extend(idea.get("research_keywords", idea.get("pubmed_keywords", [])))
    # Deduplicate while preserving order, keep top 8
    seen: set[str] = set()
    unique_keywords: list[str] = []
    for kw in all_keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique_keywords.append(kw)
        if len(unique_keywords) >= 8:
            break

    pubmed_papers = await search_pubmed(unique_keywords, limit=15)

    pubmed_context = "\n\n".join(
        f"PMID: {p.id.replace('pubmed_', '')}\nTitle: {p.title}\nAbstract: {p.abstract[:400]}"
        for p in pubmed_papers
        if p.abstract
    )
    if not pubmed_context:
        pubmed_context = "No directly matching PubMed results found for these keywords."

    # Stage 3: LLM validates technical feasibility and narrows to 3-5 ideas
    validation_messages = [
        {
            "role": "system",
            "content": (
                "You are a research scientist and innovation expert. "
                "Evaluate candidate ideas against current research literature to assess technical feasibility. "
                "Return ONLY valid JSON — no markdown, no preamble."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Research area: \"{session.query}\"\n\n"
                f"Candidate ideas:\n{json.dumps(candidates, indent=2)[:2500]}\n\n"
                f"Relevant research literature:\n{pubmed_context[:1500]}\n\n"
                "Select the 3 to 5 ideas that are BOTH:\n"
                "1. Most likely to be patentable (based on the gap analysis)\n"
                "2. Most technically feasible (supported or at least not contradicted by current research)\n\n"
                "For each selected idea, return the original fields plus:\n"
                '- "scientific_feasibility": A 2-3 sentence assessment of technical feasibility '
                "(cite specific research findings if relevant, or explain why the approach is feasible "
                "based on established science)\n"
                '- "supporting_research": Brief note on what existing research supports or informs this idea '
                "(name specific papers/fields from the research context, or note if it's a genuine frontier)\n\n"
                "Do NOT include the research_keywords field in the output.\n"
                "Return a JSON array of 3-5 ideas."
            ),
        },
    ]

    yield {"status": "Validating and ranking ideas…"}

    raw2 = await llm.chat_complete(llm.REASONING_MODEL, validation_messages, temperature=0.6, groq_api_key=groq_key, max_tokens=2000)
    try:
        ideas = _parse_json(raw2)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("Model returned malformed JSON for validated ideas")

    session_store.update_session(session.id, {"ideas": ideas})
    yield {"done": True, "ideas": ideas}


@router.post("/session/{session_id}/select-idea")
async def select_idea(session_id: str, req: SelectIdeaRequest, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.idea_index < 0 or req.idea_index >= len(session.ideas):
        raise HTTPException(status_code=400, detail="Invalid idea index")

    selected = session.ideas[req.idea_index]
    all_docs = rag.get_all_documents(session_id)
    patent_context = "\n\n---\n\n".join(
        d["text"] for d in all_docs if d["metadata"].get("type") == "patent"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a patent attorney specializing in medtech. Assess whether the proposed idea "
                "would infringe on any of the listed patents. Be specific: cite patent titles and explain "
                "the risk level. Also identify safe design-around strategies."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Proposed idea: {selected.get('title')}\n\n"
                f"Description: {selected.get('description')}\n\n"
                f"Technical approach: {selected.get('technical_approach')}\n\n"
                f"Existing patents to check against:\n{patent_context}\n\n"
                "Provide:\n"
                "1. **Infringement Risk Assessment** (Low / Medium / High) with reasoning\n"
                "2. **Specific Patent Conflicts** (if any) — which patents and which claims\n"
                "3. **Safe Design-Around Strategies** — how to ensure non-infringement\n"
                "4. **Patentability Assessment** — what aspects of this idea could be patented"
            ),
        },
    ]

    async def stream_check():
        full_response = ""
        try:
            async for chunk in llm.chat_stream(llm.REASONING_MODEL, messages, temperature=0.2, groq_api_key=groq_key):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            session_store.update_session(
                session_id,
                {
                    "selected_idea_index": req.idea_index,
                    "infringement_check": full_response,
                },
            )
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_check(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/session/{session_id}/evaluate-idea")
async def evaluate_idea(session_id: str, req: EvaluateIdeaRequest, groq_key: str = Depends(get_groq_key)):
    """
    Patent conflict check for an engineer-submitted idea.
    Requires the analysis step to have been run first (so the RAG corpus exists).
    """
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    all_docs = rag.get_all_documents(session_id)
    patent_context = "\n\n---\n\n".join(
        d["text"] for d in all_docs if d["metadata"].get("type") == "patent"
    )
    if not patent_context:
        raise HTTPException(
            status_code=400,
            detail="No patent documents found. Run the analysis step first to load the patent corpus.",
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a patent attorney specializing in medical device and technology patents. "
                "Assess whether the proposed idea would infringe on any of the listed patents. "
                "Be specific: cite patent titles and explain the risk level. "
                "Also identify safe design-around strategies and novel aspects that could be patented."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Proposed idea: {req.idea_title}\n\n"
                f"Description: {req.idea_description}\n\n"
                f"Existing patents to check against:\n{patent_context}\n\n"
                "Provide:\n"
                "1. **Infringement Risk Assessment** (Low / Medium / High) with clear reasoning\n"
                "2. **Specific Patent Conflicts** — which patents and which claims pose risks\n"
                "3. **Safe Design-Around Strategies** — how to modify the idea to ensure non-infringement\n"
                "4. **Patentability Assessment** — which aspects of this idea appear novel and potentially patentable"
            ),
        },
    ]

    async def stream_evaluation():
        full_response = ""
        try:
            async for chunk in llm.chat_stream(
                llm.REASONING_MODEL, messages, temperature=0.2, groq_api_key=groq_key
            ):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            session_store.update_session(
                session_id,
                {
                    "user_idea": {"title": req.idea_title, "description": req.idea_description},
                    "infringement_check": full_response,
                    # Clear any previously selected AI idea to avoid context confusion
                    "selected_idea_index": None,
                },
            )
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_evaluation(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
