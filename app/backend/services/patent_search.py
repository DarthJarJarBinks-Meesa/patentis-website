import httpx
from urllib.parse import quote
from models.schemas import Patent

GOOGLE_PATENTS_XHR = "https://patents.google.com/xhr/query"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://patents.google.com/",
}


async def search_google_patents(keywords: list[str], limit: int = 15) -> list[Patent]:
    query = "+".join(kw.replace(" ", "+") for kw in keywords[:6])
    url_param = quote(f"q={query}&num={limit}&language=ENGLISH")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                GOOGLE_PATENTS_XHR,
                params={"url": f"q={query}&num={limit}&language=ENGLISH"},
                headers=_HEADERS,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        print(f"Google Patents search error: {e}")
        return []

    patents = []
    for cluster in data.get("results", {}).get("cluster", []):
        for item in cluster.get("result", []):
            p = item.get("patent", {})
            pub_num = p.get("publication_number", "")
            if not pub_num:
                continue

            # Build a clean patent URL
            patent_id_path = item.get("id", f"patent/{pub_num}/en")
            url = f"https://patents.google.com/{patent_id_path}"

            # Clean up HTML entities in title
            title = p.get("title", "").replace("&hellip;", "…").replace("&amp;", "&").strip()
            if not title:
                continue

            abstract = p.get("snippet", "").replace("&hellip;", "…").strip()

            inventors = []
            raw_inv = p.get("inventor", "")
            if raw_inv:
                inventors = [i.strip() for i in raw_inv.split(";") if i.strip()]

            patents.append(
                Patent(
                    id=f"gp_{pub_num}",
                    title=title,
                    abstract=abstract,
                    filing_date=p.get("filing_date") or p.get("priority_date"),
                    assignee=p.get("assignee"),
                    inventors=inventors,
                    url=url,
                    source="uspto",
                )
            )

            if len(patents) >= limit:
                break
        if len(patents) >= limit:
            break

    return patents


# Keep EPO as optional — gracefully skipped if no credentials
async def search_epo(keywords: list[str], limit: int = 8) -> list[Patent]:
    import os
    client_id = os.getenv("EPO_CLIENT_ID", "")
    client_secret = os.getenv("EPO_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []

    EPO_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
    EPO_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                EPO_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
            )
            token_resp.raise_for_status()
            token = token_resp.json()["access_token"]

        cql_terms = " AND ".join(f'ti="{kw}"' for kw in keywords[:3])
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                EPO_SEARCH_URL,
                params={"q": cql_terms, "Range": f"1-{limit}"},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        patents = []
        results = (
            data.get("ops:world-patent-data", {})
            .get("ops:biblio-search", {})
            .get("ops:search-result", {})
            .get("ops:publication-reference", [])
        )
        if isinstance(results, dict):
            results = [results]
        for ref in results:
            doc_id = ref.get("document-id", {})
            country = doc_id.get("country", {}).get("$", "")
            number = doc_id.get("doc-number", {}).get("$", "")
            ep_id = f"{country}{number}"
            patents.append(
                Patent(
                    id=f"epo_{ep_id}",
                    title=f"EP Patent {ep_id}",
                    abstract="",
                    url=f"https://worldwide.espacenet.com/patent/search?q=pn%3D{ep_id}",
                    source="epo",
                )
            )
        return patents
    except Exception as e:
        print(f"EPO search error: {e}")
        return []
