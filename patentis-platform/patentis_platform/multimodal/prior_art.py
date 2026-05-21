"""
Prior art search — Lens.org API with Google Patents fallback.

All outputs include a legal disclaimer (decision support only).
"""

from __future__ import annotations

from typing import Any

import httpx

from patentis_platform.config import get_settings
from patentis_platform.ingestion.patent_search import PatentHit, search_google_patents

PRIOR_ART_DISCLAIMER = (
    "Decision support only — not legal advice, freedom-to-operate, or invalidity opinion. "
    "Consult qualified patent counsel before filing or launching products."
)

LENS_SCHOLARLY = "https://api.lens.org/patent/search"
LENS_PATENT = "https://api.lens.org/patent/search"


async def search_lens_patents(query: str, limit: int = 15) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.lens_api_token:
        return []

    payload = {
        "query": query,
        "size": min(limit, 50),
        "include": ["biblio", "abstract"],
    }
    headers = {
        "Authorization": f"Bearer {settings.lens_api_token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(LENS_PATENT, json=payload, headers=headers)
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception:
        return []

    hits: list[dict[str, Any]] = []
    for rec in data.get("data", [])[:limit]:
        biblio = rec.get("biblio", {}) or {}
        title = (biblio.get("invention_title") or [{}])[0]
        if isinstance(title, dict):
            title = title.get("text", "")
        abstract = ""
        abs_block = biblio.get("abstract")
        if isinstance(abs_block, list) and abs_block:
            abstract = abs_block[0].get("text", "") if isinstance(abs_block[0], dict) else str(abs_block[0])
        lens_id = rec.get("lens_id") or rec.get("id", "")
        hits.append(
            {
                "id": f"lens_{lens_id}",
                "title": str(title)[:500],
                "abstract": str(abstract)[:2000],
                "url": f"https://www.lens.org/lens/patent/{lens_id}",
                "source": "lens",
            }
        )
    return hits


def _hits_to_response(patent_hits: list[PatentHit], lens_hits: list[dict], query: str) -> dict[str, Any]:
    patents = [
        {
            "external_id": p.external_id,
            "title": p.title,
            "abstract": p.abstract,
            "url": p.url,
            "source": p.source,
        }
        for p in patent_hits
    ]
    return {
        "query": query,
        "disclaimer": PRIOR_ART_DISCLAIMER,
        "patents": patents + lens_hits,
        "total": len(patents) + len(lens_hits),
        "sources_used": sorted(
            set([p["source"] for p in patents] + (["lens"] if lens_hits else []))
        ),
    }


async def prior_art_search(query: str, keywords: list[str] | None = None, limit: int = 15) -> dict[str, Any]:
    terms = keywords or query.split()
    lens_hits = await search_lens_patents(query if len(query) > 20 else " ".join(terms[:6]), limit=limit)
    gp = await search_google_patents(terms, limit=limit)
    return _hits_to_response(gp, lens_hits, query)
