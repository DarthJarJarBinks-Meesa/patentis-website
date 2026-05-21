"""
USPTO bulk grant XML — extract claims into patents.claims_text.

Supports local .xml files (single grant or directory). For production, sync from
https://bulkdata.uspto.gov/ (Patent Grant Full Text XML).
"""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import PatentRecord
from patentis_platform.graph.build import ensure_region_for_subclass

_NS_STRIP = re.compile(r"\{[^}]+\}")


def _tag(local: str) -> str:
    return local


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _find_first(root: ET.Element, names: list[str]) -> ET.Element | None:
    for el in root.iter():
        local = _NS_STRIP.sub("", el.tag)
        if local in names:
            return el
    return None


def _find_all_local(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _NS_STRIP.sub("", el.tag) == name]


def parse_grant_xml(xml_bytes: bytes) -> dict[str, Any] | None:
    """Parse one USPTO grant XML document."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    pub_el = _find_first(root, ["doc-number", "document-id"])
    pub_num = ""
    if pub_el is not None:
        for child in pub_el.iter():
            if _NS_STRIP.sub("", child.tag) == "doc-number":
                pub_num = (child.text or "").strip()
                break
    if not pub_num:
        for el in root.iter():
            if _NS_STRIP.sub("", el.tag) == "publication-reference":
                for c in el.iter():
                    if _NS_STRIP.sub("", c.tag) == "doc-number" and c.text:
                        pub_num = c.text.strip()
                        break

    title_el = _find_first(root, ["invention-title"])
    title = _text(title_el) or "Untitled patent"

    abstract_parts = []
    for el in _find_all_local(root, "paragraph"):
        parent = el
        in_abstract = False
        for _ in range(8):
            if parent is None:
                break
            if _NS_STRIP.sub("", parent.tag) == "abstract":
                in_abstract = True
                break
            parent = next((p for p in [parent] if hasattr(parent, "getparent")), None)
        if in_abstract:
            abstract_parts.append(_text(el))
    abstract = " ".join(abstract_parts)[:8000] if abstract_parts else ""

    claim_parts: list[str] = []
    for el in _find_all_local(root, "claim"):
        claim_parts.append(_text(el))
    if not claim_parts:
        for el in _find_all_local(root, "claim-text"):
            claim_parts.append(_text(el))
    claims_text = "\n\n".join(claim_parts)[:50000] if claim_parts else None

    cpc_codes: list[str] = []
    for el in root.iter():
        local = _NS_STRIP.sub("", el.tag)
        if local in ("classification-cpc", "main-cpc", "subclass"):
            t = _text(el)
            if t and len(t) <= 16:
                cpc_codes.append(t.upper())
        if local == "section" or local == "class":
            continue
    for el in _find_all_local(root, "classification-symbol"):
        sym = _text(el)
        if sym:
            cpc_codes.append(sym.upper()[:16])

    cpc_subclass = cpc_codes[0][:8] if cpc_codes else None
    if cpc_subclass and len(cpc_subclass) > 4:
        cpc_subclass = cpc_subclass[:4]

    filing = None
    for el in _find_all_local(root, "date"):
        if el.text and len(el.text) >= 8:
            try:
                filing = date.fromisoformat(el.text[:10].replace("/", "-")[:10])
                break
            except ValueError:
                continue

    assignee = ""
    for el in _find_all_local(root, "orgname"):
        assignee = _text(el)
        if assignee:
            break

    return {
        "external_id": f"uspto_{pub_num}" if pub_num else f"uspto_{uuid.uuid4().hex[:12]}",
        "title": title,
        "abstract": abstract,
        "claims_text": claims_text,
        "description_text": abstract,
        "cpc_codes": list(dict.fromkeys(cpc_codes))[:20],
        "cpc_subclass": cpc_subclass,
        "filing_date": filing,
        "assignee": assignee or None,
        "source": "uspto_bulk",
        "url": f"https://patents.google.com/patent/US{pub_num}" if pub_num else None,
    }


def iter_xml_files(path: Path) -> Iterator[Path]:
    if path.is_file() and path.suffix.lower() in (".xml", ".sgml"):
        yield path
    elif path.is_dir():
        for p in sorted(path.rglob("*.xml")):
            yield p
        for p in sorted(path.rglob("*.sgml")):
            yield p


async def ingest_xml_path(
    session: AsyncSession,
    path: Path,
    vertical: str = "medtech",
    cpc_filter: list[str] | None = None,
) -> dict[str, int]:
    imported = skipped = no_claims = 0
    prefixes = [p.upper() for p in (cpc_filter or [])]

    for fp in iter_xml_files(path):
        try:
            parsed = parse_grant_xml(fp.read_bytes())
        except OSError:
            skipped += 1
            continue
        if not parsed:
            skipped += 1
            continue

        cpc = parsed.get("cpc_subclass")
        if prefixes and cpc and not any(cpc.startswith(p) for p in prefixes):
            skipped += 1
            continue
        if not parsed.get("claims_text"):
            no_claims += 1

        existing = await session.execute(
            select(PatentRecord).where(PatentRecord.external_id == parsed["external_id"])
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = PatentRecord(
                id=uuid.uuid4(),
                external_id=parsed["external_id"],
                title=parsed["title"],
                abstract=parsed.get("abstract") or "",
                claims_text=parsed.get("claims_text"),
                description_text=parsed.get("description_text"),
                cpc_codes=parsed.get("cpc_codes"),
                cpc_subclass=cpc,
                filing_date=parsed.get("filing_date"),
                assignee=parsed.get("assignee"),
                source=parsed["source"],
                url=parsed.get("url"),
            )
            session.add(row)
            imported += 1
        else:
            if parsed.get("claims_text"):
                row.claims_text = parsed["claims_text"]
            if parsed.get("abstract"):
                row.abstract = parsed["abstract"]
            row.cpc_codes = parsed.get("cpc_codes") or row.cpc_codes
            skipped += 1

        if cpc:
            await ensure_region_for_subclass(session, cpc, vertical=vertical)

    await session.flush()
    return {"imported": imported, "skipped": skipped, "no_claims": no_claims}


async def download_sample_grant(url: str, dest: Path) -> Path:
    """Download one grant XML for dev/testing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest
