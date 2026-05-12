import asyncio
from fastapi import APIRouter, Depends, HTTPException
from models.schemas import SearchRequest, SearchResponse
from services import session_store, llm
from services.patent_search import search_google_patents, search_epo
from services.paper_search import search_pubmed
from api.deps import get_groq_key

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, groq_key: str = Depends(get_groq_key)):
    keywords_data = await llm.extract_keywords(req.query, groq_api_key=groq_key)
    keywords: list[str] = keywords_data.get("keywords", req.query.split())
    broad_terms: list[str] = keywords_data.get("broad_terms", [])
    search_terms = keywords + broad_terms

    patents_results, epo_results, pubmed_results = await asyncio.gather(
        search_google_patents(search_terms, limit=15),
        search_epo(keywords, limit=8),
        search_pubmed(search_terms, limit=15),
        return_exceptions=True,
    )

    patents = []
    for result in [patents_results, epo_results]:
        if isinstance(result, list):
            patents.extend(result)

    papers = []
    if isinstance(pubmed_results, list):
        papers.extend(pubmed_results)

    # Deduplicate by title similarity (simple exact-title dedup)
    seen_titles: set[str] = set()
    unique_patents = []
    for p in patents:
        key = p.title.lower().strip()
        if key not in seen_titles and p.title:
            seen_titles.add(key)
            unique_patents.append(p)

    seen_titles = set()
    unique_papers = []
    for p in papers:
        key = p.title.lower().strip()
        if key not in seen_titles and p.title:
            seen_titles.add(key)
            unique_papers.append(p)

    session = session_store.create_session(req.query)
    session_store.update_session(
        session.id,
        {
            "patents": [p.model_dump() for p in unique_patents],
            "papers": [p.model_dump() for p in unique_papers],
            "selected_patent_ids": [p.id for p in unique_patents],
            "selected_paper_ids": [p.id for p in unique_papers],
        },
    )

    return SearchResponse(
        session_id=session.id,
        patents=unique_patents,
        papers=unique_papers,
        keywords=keywords_data,
    )
