"""Patent search clients — ported from patentisv1 (Google Patents + EPO OPS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import httpx

from patentis_platform.config import get_settings

GOOGLE_PATENTS_XHR = "https://patents.google.com/xhr/query"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://patents.google.com/",
}


@dataclass
class PatentHit:
    external_id: str
    title: str
    abstract: str
    url: str
    source: str
    assignee: str | None = None
    inventors: list[str] | None = None
    filing_date: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "url": self.url,
            "source": self.source,
            "assignee": self.assignee,
            "inventors": self.inventors or [],
            "filing_date": self.filing_date,
        }


async def search_google_patents(keywords: list[str], limit: int = 15) -> list[PatentHit]:
    query = "+".join(kw.replace(" ", "+") for kw in keywords[:6])
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                GOOGLE_PATENTS_XHR,
                params={"url": f"q={query}&num={limit}&language=ENGLISH"},
                headers=_HEADERS,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    patents: list[PatentHit] = []
    for cluster in data.get("results", {}).get("cluster", []):
        for item in cluster.get("result", []):
            p = item.get("patent", {})
            pub_num = p.get("publication_number", "")
            if not pub_num:
                continue
            patent_id_path = item.get("id", f"patent/{pub_num}/en")
            url = f"https://patents.google.com/{patent_id_path}"
            title = p.get("title", "").replace("&hellip;", "…").replace("&amp;", "&").strip()
            if not title:
                continue
            abstract = p.get("snippet", "").replace("&hellip;", "…").strip()
            inventors: list[str] = []
            raw_inv = p.get("inventor", "")
            if raw_inv:
                inventors = [i.strip() for i in raw_inv.split(";") if i.strip()]
            patents.append(
                PatentHit(
                    external_id=f"gp_{pub_num}",
                    title=title,
                    abstract=abstract,
                    url=url,
                    source="google_patents",
                    assignee=p.get("assignee"),
                    inventors=inventors,
                    filing_date=p.get("filing_date") or p.get("priority_date"),
                )
            )
            if len(patents) >= limit:
                break
        if len(patents) >= limit:
            break
    return patents


async def search_epo(keywords: list[str], limit: int = 8) -> list[PatentHit]:
    settings = get_settings()
    if not settings.epo_client_id or not settings.epo_client_secret:
        return []

    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    search_url = "https://ops.epo.org/3.2/rest-services/published-data/search"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(settings.epo_client_id, settings.epo_client_secret),
            )
            token_resp.raise_for_status()
            token = token_resp.json()["access_token"]

        cql_terms = " AND ".join(f'ti="{kw}"' for kw in keywords[:3])
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                search_url,
                params={"q": cql_terms, "Range": f"1-{limit}"},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        results = (
            data.get("ops:world-patent-data", {})
            .get("ops:biblio-search", {})
            .get("ops:search-result", {})
            .get("ops:publication-reference", [])
        )
        if isinstance(results, dict):
            results = [results]
        patents: list[PatentHit] = []
        for ref in results:
            doc_id = ref.get("document-id", {})
            country = doc_id.get("country", {}).get("$", "")
            number = doc_id.get("doc-number", {}).get("$", "")
            ep_id = f"{country}{number}"
            patents.append(
                PatentHit(
                    external_id=f"epo_{ep_id}",
                    title=f"EP Patent {ep_id}",
                    abstract="",
                    url=f"https://worldwide.espacenet.com/patent/search?q=pn%3D{ep_id}",
                    source="epo",
                )
            )
        return patents
    except Exception:
        return []
