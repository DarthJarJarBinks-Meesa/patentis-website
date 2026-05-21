"""Masked supervision orchestrator: subgroups → hide patents → eval → SFT / DPO JSONL."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from models.dataset_builder import export_accepted_masking_jsonl, record_to_sft_message
from models.gap_evaluator import filter_to_training_set, score_prediction
from models.masking_config import MaskingConfig
from models.masking_pipeline import build_masked_record
from models.masking_regions import eligible_cpc_subclasses
from patentis_platform.config import get_settings
from patentis_platform.db.models import MaskingRunRecord
from patentis_platform.db.session import get_session_factory

logger = logging.getLogger(__name__)

TRAINING_TRIGGER_THRESHOLD = 500
DATA_DIR = Path(__file__).parent / "data"


def write_jsonl(records: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            if "messages" in rec:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            else:
                f.write(json.dumps(record_to_sft_message(rec), ensure_ascii=False) + "\n")
            n += 1
    return n


async def run_nightly_masking_job(
    cpc_subclasses: list[str] | None = None,
    config: MaskingConfig | None = None,
) -> dict[str, Any]:
    """
    For each eligible CPC subgroup: hide 5–10 patents, generate gap brief on visible corpus,
    score against hidden claims, persist accepted/rejected, export JSONL datasets.
    """
    cfg = config or MaskingConfig.from_env()
    factory = get_session_factory()

    all_accepted: list[dict] = []
    all_rejected: list[dict] = []
    skipped_subgroups: list[str] = []

    async with factory() as session:
        subgroups = cpc_subclasses or await eligible_cpc_subclasses(session, cfg)
        if not subgroups:
            logger.warning(
                "No subgroups meet min_region_size=%s with claims_text — seed corpus or set MASKING_DEV_MODE=true",
                cfg.min_region_size,
            )

        for cpc in subgroups:
            region_accepted = 0
            for _ in range(cfg.samples_per_region):
                try:
                    record = await build_masked_record(session, cpc, cfg)
                    if record is None:
                        continue
                    result = score_prediction(record, cfg)
                    accepted, rejected = filter_to_training_set(
                        [record], [result], cfg.min_hit_rate_for_sft
                    )
                    all_accepted.extend(accepted)
                    all_rejected.extend(rejected)
                    region_accepted += len(accepted)

                    session.add(
                        MaskingRunRecord(
                            id=uuid.uuid4(),
                            cpc_subclass=cpc,
                            strategy=cfg.strategy.value,
                            accepted=len(accepted) > 0,
                            hit_rate=result.get("hit_rate"),
                            record_json={**record, "eval": result},
                        )
                    )
                    logger.info(
                        "CPC %s | hit_rate=%.2f | hits=%s/%s",
                        cpc,
                        result.get("hit_rate", 0),
                        result.get("n_hits"),
                        result.get("n_hidden"),
                    )
                except Exception as e:
                    logger.error("Masking failed for %s: %s", cpc, e)

            if region_accepted == 0 and cpc not in skipped_subgroups:
                skipped_subgroups.append(cpc)

        await session.commit()

        total_accepted = await session.scalar(
            select(func.count())
            .select_from(MaskingRunRecord)
            .where(MaskingRunRecord.accepted.is_(True))
        )
        accepted_path = DATA_DIR / "sft_masked_accepted.jsonl"
        rejected_path = DATA_DIR / "dpo_masked_rejected.jsonl"
        exported_accepted = await export_accepted_masking_jsonl(
            session, accepted_path, min_hit_rate=cfg.min_hit_rate_for_sft
        )
        exported_rejected = write_jsonl(all_rejected, rejected_path)

    trigger_training = (total_accepted or 0) >= TRAINING_TRIGGER_THRESHOLD
    if trigger_training:
        logger.info("Threshold %s reached — run: python models/train_sft.py --export", TRAINING_TRIGGER_THRESHOLD)

    return {
        "config": {
            "strategy": cfg.strategy.value,
            "min_region_size": cfg.min_region_size,
            "n_hidden": [cfg.n_hidden_min, cfg.n_hidden_max],
            "samples_per_region": cfg.samples_per_region,
        },
        "subgroups_processed": subgroups,
        "subgroups_skipped_no_accept": skipped_subgroups,
        "accepted_this_run": len(all_accepted),
        "rejected_this_run": len(all_rejected),
        "total_accepted_db": total_accepted,
        "exported_accepted": exported_accepted,
        "exported_rejected": exported_rejected,
        "training_triggered": trigger_training,
        "paths": {
            "sft": str(accepted_path),
            "dpo_rejected": str(rejected_path),
        },
    }


def submit_azure_ml_job_stub(jsonl_path: str) -> dict:
    settings = get_settings()
    if not settings.azure_ml_subscription_id:
        return {"submitted": False, "reason": "AZURE_ML_SUBSCRIPTION_ID not set"}
    return {"submitted": False, "reason": "Wire azure.ai.ml command job when ML workspace is ready"}


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    print(json.dumps(asyncio.run(run_nightly_masking_job()), indent=2))
