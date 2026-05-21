"""Score masked-gap predictions against hidden patent claims."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from models.masking_config import MaskingConfig


_EMBEDDER = None


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
    return _EMBEDDER


def _embed_texts(texts: list[str]) -> np.ndarray:
    try:
        return np.array(_get_embedder().encode(texts, normalize_embeddings=True))
    except Exception:
        # Fallback: bag-of-words hash vectors
        vecs = []
        for t in texts:
            v = np.zeros(384)
            for i, w in enumerate(t.lower().split()[:200]):
                v[i % 384] += hash(w) % 100 / 100.0
            n = np.linalg.norm(v) + 1e-9
            vecs.append(v / n)
        return np.array(vecs)


def score_prediction(record: dict[str, Any], config: MaskingConfig) -> dict[str, Any]:
    try:
        brief = record["completion"]
        if isinstance(brief, str):
            brief = json.loads(brief)
    except Exception:
        return {"hit_rate": 0.0, "scores": [], "error": "unparseable_completion"}

    prediction_text = " ".join(
        filter(
            None,
            [
                brief.get("gap_description", ""),
                brief.get("gap_summary", ""),
                brief.get("predicted_claim_space", ""),
                " ".join(brief.get("suggested_directions", []) or []),
            ],
        )
    )
    if not prediction_text.strip():
        return {"hit_rate": 0.0, "scores": [], "error": "empty_prediction"}

    hidden_claims = record.get("hidden_patent_claims") or []
    if not hidden_claims:
        return {"hit_rate": 0.0, "scores": [], "error": "no_hidden_claims"}

    embeddings = _embed_texts([prediction_text] + hidden_claims)
    pred_emb = embeddings[0]
    hidden_embs = embeddings[1:]
    scores = [float(np.dot(pred_emb, h_emb)) for h_emb in hidden_embs]
    hits = [s >= config.score_threshold for s in scores]
    hit_rate = sum(hits) / len(hits) if hits else 0.0

    return {
        "hit_rate": hit_rate,
        "scores": scores,
        "hits": hits,
        "n_hidden": len(hidden_claims),
        "n_hits": sum(hits),
    }


def filter_to_training_set(
    records: list[dict],
    eval_results: list[dict],
    min_hit_rate: float = 0.5,
) -> tuple[list[dict], list[dict]]:
    accepted, rejected = [], []
    for record, result in zip(records, eval_results):
        record["eval"] = result
        if result.get("hit_rate", 0) >= min_hit_rate:
            accepted.append(record)
        else:
            rejected.append(record)
    return accepted, rejected
