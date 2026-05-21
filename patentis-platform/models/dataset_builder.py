"""Build datasets — base SFT is public masking only; org data stays in org pipelines."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import MaskingRunRecord
from patentis_platform.enterprise.training_policy import assert_base_dataset_source


def record_to_sft_message(record: dict) -> dict:
    completion = record.get("completion", {})
    if isinstance(completion, dict):
        assistant = json.dumps(completion)
    else:
        assistant = str(completion)
    return {
        "messages": [
            {"role": "system", "content": "You are Patentis. Output a single JSON opportunity brief."},
            {"role": "user", "content": record.get("prompt", "")},
            {"role": "assistant", "content": assistant},
        ]
    }


async def export_base_sft_jsonl(
    session: AsyncSession,
    out_path: Path,
    min_hit_rate: float = 0.5,
) -> int:
    """
    Export accepted masked USPTO supervision rows ONLY — the sole source for Patentis-SFT base training.
    """
    assert_base_dataset_source("masking_run_records")

    res = await session.execute(
        select(MaskingRunRecord).where(MaskingRunRecord.accepted.is_(True))
    )
    rows = res.scalars().all()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            if row.hit_rate is not None and row.hit_rate < min_hit_rate:
                continue
            rec = row.record_json
            f.write(json.dumps(record_to_sft_message(rec), ensure_ascii=False) + "\n")
            n += 1
    return n


# Backward-compatible alias
export_accepted_masking_jsonl = export_base_sft_jsonl


async def export_briefs_jsonl(*_args, **_kwargs) -> int:
    """Customer briefs must never feed base SFT — use org_adapter_trainer instead."""
    raise RuntimeError(
        "opportunity_briefs cannot be exported for base Patentis-SFT. "
        "Use models/org_adapter_trainer.py for opted-in org LoRA training only."
    )
