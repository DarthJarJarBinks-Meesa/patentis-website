"""Hybrid retrieval: BM25 over corpus + cosine similarity on embeddings."""

from __future__ import annotations

import asyncio
from uuid import UUID

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import CorpusDocument
from patentis_platform.retrieval.embeddings import encode_texts


def tokenize(s: str) -> list[str]:
    return [t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in s).split() if t]


async def hybrid_search(
    session: AsyncSession,
    project_id: UUID,
    query: str,
    top_k: int = 8,
    bm25_weight: float = 0.35,
) -> list[dict]:
    res = await session.execute(
        select(CorpusDocument).where(CorpusDocument.project_id == project_id)
    )
    docs = list(res.scalars().all())
    if not docs:
        return []

    bodies = [d.body[:8000] for d in docs]
    tokenized_corpus = [tokenize(b) for b in bodies]
    bm25 = BM25Okapi(tokenized_corpus)
    bm_scores = np.array(bm25.get_scores(tokenize(query)), dtype=np.float64)
    if bm_scores.max() > 0:
        bm_scores = bm_scores / (bm_scores.max() + 1e-9)
    else:
        bm_scores = np.zeros_like(bm_scores)

    full_embs = await asyncio.to_thread(encode_texts, bodies)
    q_emb = (await asyncio.to_thread(encode_texts, [query]))[0]
    qn = q_emb / (np.linalg.norm(q_emb) + 1e-9)
    cos_sims = np.array(
        [float(np.dot(qn, row / (np.linalg.norm(row) + 1e-9))) for row in full_embs],
        dtype=np.float64,
    )

    fused = bm25_weight * bm_scores + (1 - bm25_weight) * cos_sims
    order = np.argsort(-fused)[:top_k]
    out = []
    for idx in order:
        d = docs[int(idx)]
        out.append(
            {
                "id": str(d.id),
                "title": d.title,
                "snippet": d.body[:500],
                "score": float(fused[int(idx)]),
            }
        )
    return out
