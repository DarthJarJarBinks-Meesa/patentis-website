import re
import httpx
from models.schemas import Paper

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SEMANTIC_SCHOLAR_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_SS_FIELDS = "title,abstract,authors,year,externalIds,openAccessPdf"


async def search_semantic_scholar(keywords: list[str], limit: int = 10) -> list[Paper]:
    query = " ".join(keywords[:6])
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                SEMANTIC_SCHOLAR_SEARCH,
                params={"query": query, "limit": limit, "fields": _SS_FIELDS},
                headers={"User-Agent": "Patentis/1.0 (research tool)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    papers = []
    for item in data.get("data", []):
        title = item.get("title", "").strip()
        if not title:
            continue
        abstract = item.get("abstract") or ""
        authors = [
            a.get("name", "") for a in item.get("authors", []) if a.get("name")
        ][:6]
        year = str(item.get("year", "")) if item.get("year") else ""
        paper_id = item.get("paperId", "")
        url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""
        papers.append(
            Paper(
                id=f"ss_{paper_id or title[:40]}",
                title=title,
                abstract=abstract,
                authors=authors,
                published=year,
                url=url,
                source="semantic_scholar",
            )
        )
    return papers


async def _esearch(terms: str, limit: int) -> list[str]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            PUBMED_ESEARCH,
            params={"db": "pubmed", "term": terms, "retmode": "json", "retmax": limit, "sort": "relevance"},
        )
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])


async def search_pubmed(keywords: list[str], limit: int = 12) -> list[Paper]:
    # Try progressively relaxed queries: 2-keyword AND, then OR across all keywords.
    pmids: list[str] = []
    if keywords:
        try:
            tight = " AND ".join(f'"{kw}"[Title/Abstract]' for kw in keywords[:2])
            pmids = await _esearch(tight, limit)
        except Exception:
            pass

    if len(pmids) < 5 and keywords:
        try:
            broad = " OR ".join(f'"{kw}"[Title/Abstract]' for kw in keywords[:5])
            pmids = await _esearch(broad, limit)
        except Exception:
            pass

    if not pmids:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            fetch_resp = await client.get(
                PUBMED_EFETCH,
                params={
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "xml",
                    "rettype": "abstract",
                },
            )
            fetch_resp.raise_for_status()
            xml = fetch_resp.text
    except Exception:
        return []

    return _parse_pubmed_xml(xml)


def _parse_pubmed_xml(xml: str) -> list[Paper]:
    papers = []
    articles = re.findall(r"<PubmedArticle>(.*?)</PubmedArticle>", xml, re.DOTALL)

    for art in articles:
        pmid_match = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
        if not pmid_match:
            continue
        pmid = pmid_match.group(1)

        title_match = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", art, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""
        if not title:
            continue

        abstract = ""
        abstract_match = re.search(r"<Abstract>(.*?)</Abstract>", art, re.DOTALL)
        if abstract_match:
            abstract = re.sub(r"<[^>]+>", " ", abstract_match.group(1))
            abstract = re.sub(r"\s+", " ", abstract).strip()

        authors = []
        for author_match in re.finditer(r"<Author[^>]*>(.*?)</Author>", art, re.DOTALL):
            a = author_match.group(1)
            last = re.search(r"<LastName>(.*?)</LastName>", a)
            first = re.search(r"<ForeName>(.*?)</ForeName>", a)
            if last:
                name = (
                    f"{first.group(1).strip()} {last.group(1).strip()}".strip()
                    if first
                    else last.group(1).strip()
                )
                authors.append(name)
            if len(authors) >= 6:
                break

        year_match = re.search(r"<PubDate>.*?<Year>(\d{4})</Year>", art, re.DOTALL)
        pub_date = year_match.group(1) if year_match else ""

        papers.append(
            Paper(
                id=f"pubmed_{pmid}",
                title=title,
                abstract=abstract,
                authors=authors,
                published=pub_date,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                source="pubmed",
            )
        )

    return papers
