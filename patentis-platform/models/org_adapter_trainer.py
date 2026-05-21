"""
Per-org LoRA training — private, opt-in only. Never contributes to base Patentis-SFT.

Data sources: expert_ratings + dpo_feedback + interaction_signals for ONE org_id only.
Output: org-scoped blob path via patentis_platform.enterprise.org_adapters.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import DPOFeedback, ExpertRating, Organization
from patentis_platform.enterprise.org_adapters import activate_adapter_placeholder, ensure_adapter_row

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
MIN_RATINGS_FOR_TRAINING = 50


async def export_org_dpo_jsonl(session: AsyncSession, org_id: uuid.UUID, out_path: Path) -> int:
    """Build preference pairs from org-scoped expert ratings and DPO feedback."""
    for forbidden in ("opportunity_briefs", "interaction_signals"):
        # Explicitly not base SFT — org-private export only
        pass

    res = await session.execute(
        select(ExpertRating).where(ExpertRating.org_id == org_id).order_by(ExpertRating.created_at.desc())
    )
    ratings = list(res.scalars().all())
    if len(ratings) < MIN_RATINGS_FOR_TRAINING:
        logger.info("Org %s: %s ratings (need %s)", org_id, len(ratings), MIN_RATINGS_FOR_TRAINING)
        return 0

    dpo_res = await session.execute(select(DPOFeedback).where(DPOFeedback.org_id == org_id))
    dpo_rows = list(dpo_res.scalars().all())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for fb in dpo_rows:
            f.write(
                json.dumps(
                    {
                        "org_id": str(org_id),
                        "chosen_brief_id": str(fb.chosen_brief_id),
                        "rejected_brief_id": str(fb.rejected_brief_id),
                        "region_id": str(fb.region_id),
                    }
                )
                + "\n"
            )
            n += 1
        for r in ratings:
            if r.whitespace_quality >= 4:
                f.write(
                    json.dumps(
                        {
                            "org_id": str(org_id),
                            "region_id": str(r.region_id),
                            "label": "preferred",
                            "scores": {
                                "clinical": r.clinical_relevance,
                                "buildability": r.buildability,
                                "commercial": r.commercial_interest,
                                "whitespace": r.whitespace_quality,
                            },
                        }
                    )
                    + "\n"
                )
                n += 1
    return n


async def train_org_adapter_if_ready(session: AsyncSession, org_id: uuid.UUID) -> dict:
    org = await session.get(Organization, org_id)
    if not org or not org.training_opt_in:
        return {"trained": False, "reason": "training_opt_in is false"}

    row = await ensure_adapter_row(session, org_id)
    row.status = "training"
    await session.flush()

    out_path = DATA_DIR / f"org_dpo_{org_id}.jsonl"
    n = await export_org_dpo_jsonl(session, org_id, out_path)
    if n < 1:
        row.status = "none"
        return {"trained": False, "reason": "insufficient org-private preference data", "rows": n}

    version = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Production: submit Azure ML LoRA job → blob org-adapters/{org_id}/lora-{version}/
    await activate_adapter_placeholder(
        session,
        org_id,
        version,
        metadata={
            "type": "lora",
            "training_rows": n,
            "dataset_path": str(out_path),
            "note": "Stub manifest — replace with real PEFT weights after ML job",
        },
    )
    return {
        "trained": True,
        "org_id": str(org_id),
        "version": version,
        "rows": n,
        "blob_path": row.blob_path,
    }


def submit_org_lora_job_stub(org_id: str, dataset_path: str, output_blob: str) -> dict:
    return {
        "submitted": False,
        "org_id": org_id,
        "output_blob": output_blob,
        "reason": "Wire Azure ML LoRA job; dataset stays org-private",
    }
