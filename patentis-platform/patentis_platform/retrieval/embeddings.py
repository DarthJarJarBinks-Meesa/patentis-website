"""Text embeddings: SentenceTransformer when optional `[full]` is installed, else deterministic vectors."""

from __future__ import annotations

import hashlib

import numpy as np

from patentis_platform.db.models import EMBED_DIM

_model = None


def _pseudo_encode(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
    for i, text in enumerate(texts):
        seed_bytes = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()[:8]
        seed = int.from_bytes(seed_bytes, "big")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(EMBED_DIM).astype(np.float32)
        v /= np.linalg.norm(v) + 1e-9
        out[i] = v
    return out


def get_embedder():
    global _model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def encode_texts(texts: list[str]) -> np.ndarray:
    m = get_embedder()
    if m is None:
        return _pseudo_encode(texts)
    return m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
