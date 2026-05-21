"""Unified literature sync: PubMed + arXiv + Semantic Scholar."""

from __future__ import annotations

from patentis_platform.ingestion.paper_search import PaperHit, search_pubmed


async def search_arxiv(keywords: list[str], limit: int = 10) -> list[PaperHit]:
    import httpx

    query = "+".join(keywords[:4])
    url = "http://export.arxiv.org/api/query"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params={"search_query": f"all:{query}", "max_results": limit})
            r.raise_for_status()
            xml = r.text
    except Exception:
        return []

    import re

    papers: list[PaperHit] = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        aid = re.search(r"<id>(.*?)</id>", entry)
        title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        if not aid or not title:
            continue
        arx_id = aid.group(1).split("/")[-1]
        papers.append(
            PaperHit(
                external_id=f"arxiv_{arx_id}",
                title=re.sub(r"\s+", " ", title.group(1)).strip(),
                abstract=re.sub(r"\s+", " ", summary.group(1)).strip()[:4000] if summary else "",
                url=f"https://arxiv.org/abs/{arx_id}",
                source="arxiv",
            )
        )
    return papers


async def search_semantic_scholar(keywords: list[str], limit: int = 10) -> list[PaperHit]:
    import httpx

    from patentis_platform.config import get_settings

    q = " ".join(keywords[:6])
    headers = {}
    settings = get_settings()
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": q, "limit": limit, "fields": "title,abstract,url,year,authors"},
                headers=headers,
            )
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception:
        return []

    papers: list[PaperHit] = []
    for item in data.get("data", []):
        pid = item.get("paperId", "")
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        papers.append(
            PaperHit(
                external_id=f"s2_{pid}",
                title=item.get("title", ""),
                abstract=(item.get("abstract") or "")[:4000],
                url=item.get("url") or f"https://www.semanticscholar.org/paper/{pid}",
                source="semantic_scholar",
                authors=authors,
                published=str(item.get("year") or ""),
            )
        )
    return papers


async def search_all_literature(keywords: list[str], limit_per_source: int = 10) -> list[PaperHit]:
    import asyncio

    pubmed, arxiv, s2 = await asyncio.gather(
        search_pubmed(keywords, limit=limit_per_source),
        search_arxiv(keywords, limit=limit_per_source),
        search_semantic_scholar(keywords, limit=limit_per_source),
        return_exceptions=True,
    )
    out: list[PaperHit] = []
    for batch in (pubmed, arxiv, s2):
        if isinstance(batch, list):
            out.extend(batch)
    return out
