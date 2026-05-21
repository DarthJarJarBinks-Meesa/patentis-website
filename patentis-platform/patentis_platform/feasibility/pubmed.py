"""PubMed-based scientific feasibility proxy."""

from __future__ import annotations

import httpx

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


async def feasibility_from_keywords(keywords: list[str], limit: int = 20) -> dict[str, Any]:
    terms = " AND ".join(f'"{kw}"[Title/Abstract]' for kw in keywords[:6] if kw)
    if not terms:
        return {"score": 0.0, "hit_count": 0, "pmids": []}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(
                PUBMED_ESEARCH,
                params={
                    "db": "pubmed",
                    "term": terms,
                    "retmode": "json",
                    "retmax": limit,
                    "sort": "relevance",
                },
            )
            r.raise_for_status()
            pmids = r.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        return {"score": 0.0, "hit_count": 0, "pmids": []}

    n = len(pmids)
    # Simple proxy: saturate at 20 hits for score 1.0
    score = min(1.0, n / 12.0)
    return {"score": score, "hit_count": n, "pmids": pmids[:limit]}
