"""Persist v1-style search hits into project corpus + global patent index."""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import CorpusDocument, PatentRecord
from patentis_platform.ingestion.patent_search import PatentHit
from patentis_platform.ingestion.paper_search import PaperHit
from patentis_platform.retrieval.embeddings import encode_texts


def _dedupe_by_title(items: list, title_attr: str = "title") -> list:
    seen: set[str] = set()
    out = []
    for item in items:
        key = getattr(item, title_attr, "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


async def persist_search_hits(
    session: AsyncSession,
    project_id: UUID,
    patents: list[PatentHit],
    papers: list[PaperHit],
) -> dict[str, int]:
    patents = _dedupe_by_title(patents)
    papers = _dedupe_by_title(papers)

    patent_bodies = [f"{p.title}\n{p.abstract}" for p in patents]
    paper_bodies = [f"{p.title}\n{p.abstract}" for p in papers]
    all_bodies = patent_bodies + paper_bodies
    embs = list(await asyncio.to_thread(encode_texts, all_bodies)) if all_bodies else []
    patent_embs = embs[: len(patents)]
    paper_embs = embs[len(patents) :]

    n_patents = 0
    for i, p in enumerate(patents):
        emb = patent_embs[i] if i < len(patent_embs) else None
        existing = await session.execute(
            select(PatentRecord).where(PatentRecord.external_id == p.external_id)
        )
        if existing.scalar_one_or_none() is None:
            session.add(
                PatentRecord(
                    id=uuid.uuid4(),
                    external_id=p.external_id,
                    title=p.title,
                    abstract=p.abstract[:4000],
                    assignee=p.assignee,
                    source=p.source,
                    url=p.url,
                    embedding=emb.tolist() if emb is not None else None,
                )
            )
        session.add(
            CorpusDocument(
                id=uuid.uuid4(),
                project_id=project_id,
                title=p.title[:512],
                body=f"{p.title}\n{p.abstract}"[:8000],
                source_type="patent",
                metadata_json=p.to_metadata(),
                embedding=emb.tolist() if emb is not None else None,
            )
        )
        n_patents += 1

    n_papers = 0
    for i, paper in enumerate(papers):
        emb = paper_embs[i] if i < len(paper_embs) else None
        session.add(
            CorpusDocument(
                id=uuid.uuid4(),
                project_id=project_id,
                title=paper.title[:512],
                body=f"{paper.title}\n{paper.abstract}"[:8000],
                source_type="paper",
                metadata_json=paper.to_metadata(),
                embedding=emb.tolist() if emb is not None else None,
            )
        )
        n_papers += 1

    await session.flush()
    return {"patents": n_patents, "papers": n_papers}
