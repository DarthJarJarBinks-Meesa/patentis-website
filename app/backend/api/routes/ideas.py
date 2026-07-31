import json
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from services import session_store, llm, rag
from services.paper_search import search_pubmed
from services.conference_search import search_conference_papers, CONFERENCE_YEARS_BACK
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
    # Truncated array recovery: find all complete {...} objects inside a partial [...]
    array_start = text.find("[")
    if array_start != -1:
        objects = []
        depth = 0
        obj_start = None
        for i, ch in enumerate(text[array_start:], array_start):
            if ch == "{":
                if depth == 0:
                    obj_start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and obj_start is not None:
                    try:
                        obj = json.loads(text[obj_start : i + 1])
                        objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    obj_start = None
        if objects:
            return objects
    raise json.JSONDecodeError("Could not extract JSON", text, 0)


def _build_fto_messages(title: str, description: str, patent_context: str, technical_approach: str = "") -> list[dict]:
    concept = f"Design concept: {title}\n\nDescription: {description}\n\n"
    if technical_approach:
        concept += f"Technical approach: {technical_approach}\n\n"

    return [
        {
            "role": "system",
            "content": (
                "You are a patent research assistant generating structured FTO (Freedom to Operate) "
                "landscape reports for medtech R&D engineers. Your output will be handed directly to "
                "patent counsel. EVERY flagged element must cite a specific, verifiable patent number "
                "and the exact relevant claim or passage. Never make an unsourced assertion. "
                "Only cite patent numbers that literally appear in the patent corpus provided below — "
                "never invent, guess, or recall a patent number from general knowledge. If the corpus "
                "doesn't contain a patent relevant to an element, say so plainly instead of citing one. "
                "Use exactly three confidence levels: 'Likely blocked', 'Worth reviewing', 'Appears clear'."
            ),
        },
        {
            "role": "user",
            "content": (
                concept
                + f"Patent corpus:\n{patent_context}\n\n"
                "Generate a structured FTO landscape report:\n\n"
                "## Patent Landscape Summary\n"
                "2-3 bullet points on patent density and key assignees in this space.\n\n"
                "## Relevant Patents Found\n"
                "For each relevant patent:\n"
                "**[Patent Number]** — Title (Assignee, Year)\n"
                "Relevant claim/passage: [specific claim text or close paraphrase with claim number]\n"
                "Relevance: [1 sentence]\n\n"
                "## FTO Element-by-Element Analysis\n"
                "For each distinct technical element of the proposed concept:\n"
                "**Element**: [specific technical element]\n"
                "**Assessment**: Likely blocked | Worth reviewing | Appears clear\n"
                "**Basis**: [Patent number + claim number or passage — required for every non-clear flag]\n\n"
                "Before flagging anything as 'Worth reviewing', do the full comparison yourself: read the "
                "specific claim language in the patent corpus, compare it element-by-element against the "
                "proposed concept, and state your own conclusion about whether it conflicts. Never respond "
                "with an instruction for the user to 'research this further' or 'check if this is patented' — "
                "you have the patent corpus already; do that work now and report the result. Reserve 'Worth "
                "reviewing' for cases where you've done this comparison and genuine ambiguity remains "
                "(e.g. claim scope is contested or depends on facts not in the corpus), not as a stand-in "
                "for analysis you haven't done.\n\n"
                "Definitions: 'Likely blocked' = direct overlap with existing claims; "
                "'Worth reviewing' = possible overlap, attorney review needed; "
                "'Appears clear' = no direct overlap in searched corpus.\n\n"
                "## Design-Around Strategies\n"
                "For 'Likely blocked' or 'Worth reviewing' elements, specific modifications to avoid infringement.\n\n"
                "## Patentability Assessment\n"
                "Which elements appear novel and potentially patentable, with reasoning.\n\n"
                "## Search Scope & Limitations\n"
                "State: 'This FTO analysis covers US patents and EPO/PCT filings in the searched corpus. "
                "It is a research triage tool, not a legal opinion. All findings should be reviewed "
                "by qualified patent counsel before any filing or commercialization decision.'"
            ),
        },
    ]


_FTO_ASSESSMENT_RE = re.compile(r"\*\*Assessment\*\*:\s*(Likely blocked|Worth reviewing|Appears clear)", re.IGNORECASE)


def _assess_fto_clearance(report: str) -> dict:
    """Tally the per-element **Assessment** lines in an FTO report into a verdict.
    'Mostly clear' means no element was flagged as an outright block and clear
    elements outnumber (or match) the ones merely worth reviewing."""
    labels = [m.lower() for m in _FTO_ASSESSMENT_RE.findall(report)]
    blocked = labels.count("likely blocked")
    review = labels.count("worth reviewing")
    clear = labels.count("appears clear")
    total = len(labels)
    mostly_clear = total > 0 and blocked == 0 and clear >= review
    if total == 0:
        label = "Unassessed"
    elif blocked > 0:
        label = "Likely blocked"
    elif mostly_clear:
        label = "Appears clear"
    else:
        label = "Worth reviewing"
    return {"blocked": blocked, "review": review, "clear": clear, "total": total, "mostly_clear": mostly_clear, "label": label}


def _compact_patent_summaries(session_id: str, limit: int = 12, char_limit: int = 220) -> str:
    docs = [d for d in rag.get_all_documents(session_id) if d["metadata"].get("type") == "patent"]
    if not docs:
        return "No patents loaded for this session yet."
    lines = []
    for d in docs[:limit]:
        text = d["text"].replace("\n", " ")
        lines.append(f"- {text[:char_limit]}{'…' if len(text) > char_limit else ''}")
    return "\n".join(lines)


async def _run_fto_check(idea: dict, session_id: str, groq_key: str) -> tuple[str, dict]:
    """Semantically pull the patents most relevant to this specific idea (rather than
    dumping the whole corpus) and run it through the same FTO report used for
    user-selected ideas, so the filter applied here matches what the user sees later."""
    query = f"{idea.get('title', '')} {idea.get('key_innovation', '')} {idea.get('technical_approach', '')}"
    relevant = rag.query_collection(session_id, query, n_results=12)
    patent_context = "\n\n---\n\n".join(
        d["text"] for d in relevant if d["metadata"].get("type") == "patent"
    )
    if not patent_context:
        patent_context = "No patents relevant to this concept's specific technical elements were found in the corpus."

    messages = _build_fto_messages(
        title=idea.get("title", ""),
        description=idea.get("description", ""),
        patent_context=patent_context,
        technical_approach=idea.get("technical_approach", ""),
    )
    report = await llm.chat_complete(llm.REASONING_MODEL, messages, temperature=0.2, groq_api_key=groq_key, max_tokens=800)
    return report, _assess_fto_clearance(report)


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


FTO_TARGET_IDEAS = 2


async def _generate_ideas_stream(session, groq_key: str = ""):
    yield {"status": "Generating candidate ideas…"}

    patent_summaries = _compact_patent_summaries(session.id)

    # Stage 1: Generate 7 candidate ideas, grounded in both the gap analysis and the
    # actual patents pulled for this session — not just the analysis summary — so
    # candidates are steered away from what's already patented from the start.
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
                f"Patents already pulled for this session (do not propose ideas that replicate these):\n"
                f"{patent_summaries}\n\n"
                "Generate exactly 4 novel product/technology ideas that:\n"
                "1. Specifically fill the identified patent gaps\n"
                "2. Are technically feasible\n"
                "3. Have clear commercial or societal potential\n"
                "4. Do NOT replicate any patented approach listed above\n\n"
                "Return a JSON array:\n"
                "[\n"
                "  {\n"
                '    "title": "Short descriptive name",\n'
                '    "tagline": "One sentence value proposition",\n'
                '    "description": "1-2 sentence technical overview",\n'
                '    "key_innovation": "The specific novel element that makes this patentable",\n'
                '    "target_market": "Who needs this and why",\n'
                '    "technical_approach": "2-3 sentence explanation of how it works",\n'
                '    "why_unpatented": "Specific reason this approach is not covered by existing patents",\n'
                '    "research_keywords": ["keyword1", "keyword2", "keyword3"]\n'
                "  }\n"
                "]\n\n"
                'Include 3-4 precise technical terms in "research_keywords" '
                "that would find relevant research papers validating the scientific basis of the idea."
            ),
        },
    ]

    raw = await llm.chat_complete(llm.REASONING_MODEL, candidate_messages, temperature=0.85, groq_api_key=groq_key, max_tokens=2500)
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

    yield {"status": "Scanning recent conference proceedings…"}

    # Recent conference papers surface new materials/designs faster than journal
    # publication cycles — use them both to sharpen idea validation below and,
    # via the RAG embed, to inform later product-development consulting in chat.
    conference_papers = await search_conference_papers(unique_keywords, query=session.query)

    conference_context = "\n\n".join(
        f"Venue: {p.venue or 'Unknown venue'} ({p.published or 'n.d.'})\nTitle: {p.title}\nAbstract: {p.abstract[:400]}"
        for p in conference_papers
        if p.abstract
    )
    if not conference_context:
        conference_context = "No recent conference papers found for these keywords."

    if conference_papers:
        conference_docs = [
            {
                "id": paper.id,
                "text": (
                    f"CONFERENCE PAPER ({paper.venue or 'Unknown venue'}, {paper.published or 'n.d.'}): "
                    f"{paper.title}\n\nAbstract: {paper.abstract}"
                ),
                "metadata": {
                    "type": "conference",
                    "title": paper.title,
                    "source": paper.source,
                    "venue": paper.venue or "",
                },
            }
            for paper in conference_papers
        ]
        rag.embed_documents(session.id, conference_docs)

    # Stage 3: LLM ranks ALL candidates by patentability + technical feasibility.
    # Nothing is discarded here — the FTO filter in stage 4 makes the real cut.
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
                f"Recent conference papers (last {CONFERENCE_YEARS_BACK} years) on related materials/designs:\n{conference_context[:1500]}\n\n"
                f"Rank all {len(candidates)} ideas from strongest to weakest, based on BOTH:\n"
                "1. Likely patentability (based on the gap analysis)\n"
                "2. Technical feasibility (supported or at least not contradicted by current research)\n\n"
                "Where a recent conference paper describes a new material, design, or method that would make "
                "a candidate idea stronger, more novel, or technically sharper, incorporate that insight into "
                "the idea's description and technical_approach — don't just use conference papers as a feasibility "
                "check, use them as inspiration to improve the idea itself.\n\n"
                "For every idea, return the original fields plus:\n"
                '- "scientific_feasibility": A 2-3 sentence assessment of technical feasibility '
                "(cite specific research findings if relevant, or explain why the approach is feasible "
                "based on established science)\n"
                '- "supporting_research": Brief note on what existing research and recent conference findings '
                "support or inform this idea (name specific papers/venues from the context above, or note if "
                "it's a genuine frontier)\n\n"
                "Do NOT include the research_keywords field in the output.\n"
                f"Return a JSON array of all {len(candidates)} ideas, ordered strongest first."
            ),
        },
    ]

    yield {"status": "Ranking ideas by patentability and feasibility…"}

    raw2 = await llm.chat_complete(llm.REASONING_MODEL, validation_messages, temperature=0.6, groq_api_key=groq_key, max_tokens=1500)
    try:
        ranked_ideas = _parse_json(raw2)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("Model returned malformed JSON for ranked ideas")

    # Stage 4: run each ranked idea through the FTO filter against the patent corpus,
    # strongest first, stopping once enough of them come back mostly clear.
    accepted: list[dict] = []
    for i, idea in enumerate(ranked_ideas):
        title = idea.get("title", f"Idea {i + 1}")
        yield {"status": f"Checking freedom-to-operate for “{title}” ({i + 1}/{len(ranked_ideas)})…"}
        report, clearance = await _run_fto_check(idea, session.id, groq_key)
        idea["fto_report"] = report
        idea["fto_clearance"] = clearance
        if clearance["mostly_clear"]:
            accepted.append(idea)
            yield {"status": f"“{title}” appears clear of the patent corpus."}
            if len(accepted) >= FTO_TARGET_IDEAS:
                break
        else:
            yield {"status": f"“{title}” — {clearance['label'].lower()} — trying the next idea…"}

    if len(accepted) < FTO_TARGET_IDEAS:
        # Checked every candidate and still came up short of the target — fill out
        # with the least-encumbered leftovers rather than returning fewer ideas.
        accepted_ids = {id(idea) for idea in accepted}
        leftovers = sorted(
            (idea for idea in ranked_ideas if id(idea) not in accepted_ids),
            key=lambda idea: (idea["fto_clearance"]["blocked"], idea["fto_clearance"]["review"]),
        )
        accepted.extend(leftovers[: FTO_TARGET_IDEAS - len(accepted)])

    session_store.update_session(session.id, {"ideas": accepted})
    yield {"done": True, "ideas": accepted}


@router.post("/session/{session_id}/select-idea")
async def select_idea(session_id: str, req: SelectIdeaRequest, groq_key: str = Depends(get_groq_key)):
    try:
        session = session_store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.idea_index < 0 or req.idea_index >= len(session.ideas):
        raise HTTPException(status_code=400, detail="Invalid idea index")

    selected = session.ideas[req.idea_index]
    cached_report = selected.get("fto_report")

    async def stream_check():
        try:
            if cached_report:
                # Idea generation already ran this exact concept through the FTO filter
                # (see stage 4 of _generate_ideas_stream) — reuse it instead of paying
                # for the same check twice.
                full_response = cached_report
                yield f"data: {json.dumps({'content': full_response})}\n\n"
            else:
                all_docs = rag.get_all_documents(session_id)
                patent_context = "\n\n---\n\n".join(
                    d["text"] for d in all_docs if d["metadata"].get("type") == "patent"
                )
                messages = _build_fto_messages(
                    title=selected.get("title"),
                    description=selected.get("description"),
                    patent_context=patent_context,
                    technical_approach=selected.get("technical_approach"),
                )
                full_response = ""
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

    messages = _build_fto_messages(
        title=req.idea_title,
        description=req.idea_description,
        patent_context=patent_context,
    )

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
