"""Extract text from patent PDFs (text layer)."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 40) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    parts: list[str] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(f"--- Page {i + 1} ---\n{t.strip()}")
    return "\n\n".join(parts)


def segment_claim_blocks(full_text: str) -> dict[str, str]:
    """
    Heuristic split for US-style claims section.
    """
    lowered = full_text.lower()
    idx = lowered.find("claims")
    if idx == -1:
        return {"claims": "", "remainder": full_text[:20000]}
    return {"claims": full_text[idx : idx + 25000], "remainder": full_text[:idx][-12000:]}
