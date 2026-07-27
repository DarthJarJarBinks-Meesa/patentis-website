from fastapi import APIRouter, Depends
from models.schemas import ConferenceSearchRequest, ConferenceSearchResponse
from services import llm
from services.conference_registry import CONFERENCE_REGISTRY
from services.conference_search import (
    CONFERENCE_SEARCH_LIMIT,
    CONFERENCE_YEARS_BACK,
    search_conference_papers,
)
from api.deps import get_groq_key

router = APIRouter()


@router.get("/conferences/domains")
async def list_conference_domains():
    return {"domains": list(CONFERENCE_REGISTRY.keys())}


@router.post("/search/conferences", response_model=ConferenceSearchResponse)
async def search_conferences(req: ConferenceSearchRequest, groq_key: str = Depends(get_groq_key)):
    """Standalone Boolean + semantic search over recent medtech conference proceedings.

    Query understanding (NL -> keywords) reuses the same extraction the main patent/paper
    search uses, so the same natural-language query works across all three searches.
    """
    keywords_data = await llm.extract_keywords(req.query, groq_api_key=groq_key)
    keywords: list[str] = keywords_data.get("keywords", req.query.split())
    broad_terms: list[str] = keywords_data.get("broad_terms", [])

    results = await search_conference_papers(
        keywords=keywords + broad_terms,
        query=req.query,
        years_back=req.years_back or CONFERENCE_YEARS_BACK,
        limit=req.limit or CONFERENCE_SEARCH_LIMIT,
        domains=req.domains,
        venue_only=req.venue_only,
    )

    return ConferenceSearchResponse(
        results=results,
        keywords=keywords_data,
        domains_available=list(CONFERENCE_REGISTRY.keys()),
    )
