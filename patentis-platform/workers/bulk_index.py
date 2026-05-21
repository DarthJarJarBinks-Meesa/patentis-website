"""Bulk USPTO XML ingest worker."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from patentis_platform.config import get_settings
from patentis_platform.db.session import get_session_factory
from patentis_platform.graph.build import rebuild_region_counts
from patentis_platform.ingestion.uspto_bulk import ingest_xml_path


async def run(path: str, vertical: str = "medtech") -> dict:
    settings = get_settings()
    prefixes = [p.strip() for p in settings.medtech_cpc_prefixes.split(",") if p.strip()]
    factory = get_session_factory()
    async with factory() as session:
        stats = await ingest_xml_path(session, Path(path), vertical=vertical, cpc_filter=prefixes)
        await rebuild_region_counts(session)
        await session.commit()
    return stats


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("xml_path", help="Directory or file of USPTO grant XML")
    p.add_argument("--vertical", default="medtech")
    args = p.parse_args()
    print(asyncio.run(run(args.xml_path, args.vertical)))
