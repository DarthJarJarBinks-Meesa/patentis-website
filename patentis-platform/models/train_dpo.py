"""DPO training stub — run when expert_rating / rejected masking pairs exist."""

from __future__ import annotations

import json
from pathlib import Path


def build_dpo_pairs_from_rejected(rejected_jsonl: Path, out_path: Path) -> int:
    if not rejected_jsonl.exists():
        return 0
    n = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rejected_jsonl.open() as fin, out_path.open("w") as fout:
        for line in fin:
            if not line.strip():
                continue
            rec = json.loads(line)
            fout.write(
                json.dumps(
                    {
                        "prompt": rec.get("prompt", ""),
                        "chosen": rec.get("completion", {}),
                        "rejected": {"gap_description": "low quality", "confidence": 0.1},
                    }
                )
                + "\n"
            )
            n += 1
    return n


if __name__ == "__main__":
    data = Path(__file__).parent / "data"
    n = build_dpo_pairs_from_rejected(data / "dpo_masked_rejected.jsonl", data / "dpo_pairs.jsonl")
    print(f"built {n} DPO pairs")
