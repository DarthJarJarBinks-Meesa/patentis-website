"""Keyword extraction for parallel patent/literature search."""

from __future__ import annotations

import re

from patentis_platform.synthesis.router import chat_json


async def extract_search_keywords(query: str) -> dict:
    """Return keywords, broad_terms, cpc_hints — LLM when configured, else heuristic."""
    system = (
        "You are a patent search expert. Return ONLY valid JSON with keys: "
        "keywords (5-8 technical terms), broad_terms (2-3), cpc_hints (1-3 CPC codes like A61B)."
    )
    user = f'Extract patent search keywords from: "{query}"'
    data = await chat_json(system, user, temperature=0.1)
    if data and isinstance(data.get("keywords"), list):
        return {
            "keywords": [str(k) for k in data["keywords"][:8]],
            "broad_terms": [str(k) for k in (data.get("broad_terms") or [])[:3]],
            "cpc_hints": [str(k) for k in (data.get("cpc_hints") or [])[:3]],
        }

    tokens = [t for t in re.split(r"[^\w]+", query.lower()) if len(t) > 3][:8]
    if not tokens:
        tokens = query.split()[:6]
    return {"keywords": tokens, "broad_terms": tokens[:2], "cpc_hints": []}
