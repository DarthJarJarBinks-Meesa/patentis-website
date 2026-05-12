import re
import httpx
from models.schemas import Paper

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


async def search_pubmed(keywords: list[str], limit: int = 12) -> list[Paper]:
    # Build a focused query using title/abstract fields
    terms = " AND ".join(f'"{kw}"[Title/Abstract]' for kw in keywords[:4])

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            search_resp = await client.get(
                PUBMED_ESEARCH,
                params={
                    "db": "pubmed",
                    "term": terms,
                    "retmode": "json",
                    "retmax": limit,
                    "sort": "relevance",
                },
            )
            search_resp.raise_for_status()
            pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"PubMed search error: {e}")
        return []

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
    except Exception as e:
        print(f"PubMed fetch error: {e}")
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
