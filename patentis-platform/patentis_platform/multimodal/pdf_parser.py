"""Patent PDF layout extraction (text layer + figure reference detection)."""

from __future__ import annotations

import re

from patentis_platform.multimodal.pdf_extract import extract_pdf_text, segment_claim_blocks

_FIG_REF = re.compile(r"\b(?:FIG\.?|FIGURE)\s*(\d+[A-Za-z]?)\b", re.IGNORECASE)


def parse_patent_pdf(pdf_bytes: bytes) -> dict:
    full = extract_pdf_text(pdf_bytes)
    segments = segment_claim_blocks(full)
    fig_nums = sorted(set(_FIG_REF.findall(full)))
    return {
        "full_text_len": len(full),
        "claims_excerpt": segments.get("claims", "")[:25000],
        "description_excerpt": segments.get("remainder", "")[:25000],
        "figure_refs": fig_nums[:30],
    }
