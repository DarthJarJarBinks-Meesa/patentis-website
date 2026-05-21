"""
Patentis-SFT v1 — export datasets and optional local fine-tune stub.

  python models/train_sft.py --export
  python models/train_sft.py --train-local  # requires transformers + GPU
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

SAMPLE = {
    "messages": [
        {"role": "system", "content": "You are Patentis. Output a single JSON opportunity brief."},
        {"role": "user", "content": "CPC A61F implant micromotion sensing whitespace."},
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "title": "Implant micromotion monitoring gap",
                    "gap_summary": "Low density in capacitive strain sensing for loosening.",
                    "why_exists": "Fragmented assignees; recent filing momentum.",
                    "assignee_landscape": "No dominant player >15% share.",
                    "enabling_science": "PubMed shows feasibility of wireless strain telemetry.",
                    "product_directions": ["Smart stem with passive RFID backscatter"],
                    "confidence": 0.62,
                    "disclaimers": "Decision support only.",
                }
            ),
        },
    ]
}

DATA_DIR = Path(__file__).parent / "data"


async def export_all() -> dict:
    from models.dataset_builder import export_base_sft_jsonl
    from patentis_platform.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        n_mask = await export_base_sft_jsonl(session, DATA_DIR / "sft_masked_accepted.jsonl")

    sample_path = DATA_DIR / "sft_sample.jsonl"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    with sample_path.open("w") as f:
        f.write(json.dumps(SAMPLE) + "\n")

    holdout = DATA_DIR / "eval_medtech_holdout.jsonl"
    if not holdout.exists():
        holdout.write_text(
            json.dumps(
                {
                    "messages": SAMPLE["messages"],
                    "hidden_patent_claims": ["wireless strain sensing implant telemetry claim 1"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    return {
        "masking_rows": n_mask,
        "policy": "base_sft_public_uspto_masked_only",
        "customer_briefs_exported": 0,
        "sample": str(sample_path),
    }


def train_local_stub(jsonl_path: Path) -> dict:
    try:
        from transformers import Trainer, TrainingArguments  # noqa: F401
    except ImportError:
        return {"trained": False, "reason": "pip install transformers datasets accelerate"}
    return {
        "trained": False,
        "reason": "Wire Trainer + base model in Azure ML; local stub validates deps only",
        "dataset": str(jsonl_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--train-local", action="store_true")
    args = parser.parse_args()

    if args.export or not args.train_local:
        out = asyncio.run(export_all())
        print(json.dumps(out, indent=2))

    if args.train_local:
        path = DATA_DIR / "sft_masked_accepted.jsonl"
        if not path.exists():
            path = DATA_DIR / "sft_sample.jsonl"
        print(json.dumps(train_local_stub(path), indent=2))


if __name__ == "__main__":
    main()
