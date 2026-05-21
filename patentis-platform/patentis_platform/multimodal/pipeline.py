"""Multimodal brief: PDF text + placeholder for figure-level vision."""

from __future__ import annotations

from patentis_platform.multimodal.pdf_extract import extract_pdf_text, segment_claim_blocks


async def brief_from_pdf_bytes(pdf_bytes: bytes, region_label: str) -> dict:
    full = extract_pdf_text(pdf_bytes)
    segments = segment_claim_blocks(full)
    # Future: rasterize pages → chat_vision_caption from synthesis.router
    return {
        "region": region_label,
        "claims_excerpt": segments["claims"][:8000],
        "description_excerpt": segments["remainder"][:8000],
        "figure_captions": "Figure-level vision deferred — ingest raster pages or Azure DI layouts.",
    }
