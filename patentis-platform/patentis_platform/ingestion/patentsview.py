"""
PatentsView Search API v1 client (async).
https://search.patentsview.org/docs/
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

PVS_QUERY = "https://search.patentsview.org/api/v1/patent/query"


async def query_patents_by_cpc_subclass(prefix: str, per_page: int = 60) -> list[dict[str, Any]]:
    """
    prefix e.g. A61B — matches CPC subclass starting with this string.
    """
    body = {
        "q": {"cpc_subclass_id": prefix},
        "f": [
            "patent_number",
            "patent_title",
            "patent_abstract",
            "patent_date",
            "patent_type",
            "assignee_organization",
            "cpc_subgroup_id",
        ],
        "o": {"page": 1, "per_page": min(per_page, 100)},
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(PVS_QUERY, json=body)
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception:
        return []

    patents = []
    total = []
    try:
        if isinstance(data.get("patents"), list):
            total = data["patents"]
        elif isinstance(data.get("data"), list):  # alt shape
            total = data["data"]
        elif isinstance(data.get("output"), dict):
            hits = data["output"].get("patents") or data["output"].get("data") or []
            total = hits if isinstance(hits, list) else []
    except Exception:
        return []

    for row in total:
        if isinstance(row, dict):
            patents.append(row)
        elif isinstance(row, list):
            patents.append(dict(zip(["patent_number", "patent_title", "patent_date"], row[:10])))
    return patents


def row_to_external_id(row: dict[str, Any]) -> str:
    return str(row.get("patent_number") or row.get("id") or row.get("document_number") or "")


def row_to_title(row: dict[str, Any]) -> str:
    return str(row.get("patent_title") or row.get("title") or "")


def row_to_abstract(row: dict[str, Any]) -> str:
    return str(row.get("patent_abstract") or row.get("abstract") or "")


def row_to_assignee(row: dict[str, Any]) -> str | None:
    a = row.get("assignee_organization") or row.get("assignee") or ""
    return str(a) if a else None


def row_to_cpc_subclass(row: dict[str, Any], fallback_prefix: str) -> str:
    subgroup = row.get("cpc_subgroup_id") or row.get("cpcSubclass") or ""
    s = str(subgroup).strip().upper()
    if len(s) >= 4:
        return s[:4]
    return fallback_prefix[:4]


def parse_filing_date(row: dict[str, Any]):
    raw = row.get("patent_date") or row.get("filing_date")
    if not raw:
        return None
    if isinstance(raw, str) and len(raw) >= 8:
        try:
            return datetime.strptime(raw[:10].replace("/", "-"), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None
