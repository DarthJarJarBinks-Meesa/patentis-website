"""Extract independent and dependent claims from full claims text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClaimBlock:
    number: int
    text: str
    is_independent: bool


_CLAIM_START = re.compile(r"^\s*(\d+)\.\s+", re.MULTILINE)


def segment_claims(claims_text: str) -> list[ClaimBlock]:
    if not claims_text or not claims_text.strip():
        return []

    parts = _CLAIM_START.split(claims_text)
    if len(parts) < 2:
        return [ClaimBlock(number=1, text=claims_text.strip()[:12000], is_independent=True)]

    blocks: list[ClaimBlock] = []
    i = 1
    while i < len(parts) - 1:
        try:
            num = int(parts[i])
        except ValueError:
            i += 1
            continue
        body = parts[i + 1].strip()[:12000]
        dep = "claim" in body.lower()[:120] and num > 1
        blocks.append(ClaimBlock(number=num, text=body, is_independent=not dep))
        i += 2

    if not blocks:
        return [ClaimBlock(number=1, text=claims_text[:12000], is_independent=True)]
    return blocks


def independent_claims_text(claims_text: str, max_chars: int = 16000) -> str:
    blocks = segment_claims(claims_text)
    ind = [b for b in blocks if b.is_independent] or blocks[:3]
    out = "\n\n".join(f"Claim {b.number}: {b.text}" for b in ind)
    return out[:max_chars]
