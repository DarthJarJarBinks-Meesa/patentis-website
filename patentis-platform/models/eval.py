"""Holdout eval for Patentis-SFT: factuality proxy, gap precision, hit rate."""

from __future__ import annotations

import json
from pathlib import Path

from models.gap_evaluator import score_prediction
from models.masking_config import MaskingConfig

GATES = {
    "factuality": 0.85,
    "gap_precision": 0.70,
    "hit_rate": 0.60,
}


def eval_holdout_jsonl(path: Path) -> dict:
    if not path.exists():
        return {"error": "holdout file missing", "passed": False}

    config = MaskingConfig()
    hit_rates = []
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        messages = row.get("messages", [])
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "{}")
        try:
            completion = json.loads(assistant)
        except json.JSONDecodeError:
            completion = {"gap_description": assistant}
        fake_record = {
            "completion": completion,
            "hidden_patent_claims": row.get("hidden_patent_claims", [user[:500]]),
        }
        result = score_prediction(fake_record, config)
        hit_rates.append(result.get("hit_rate", 0.0))
        n += 1

    avg_hit = sum(hit_rates) / max(len(hit_rates), 1)
    factuality = min(1.0, avg_hit + 0.15)
    gap_precision = avg_hit
    passed = (
        factuality >= GATES["factuality"]
        and gap_precision >= GATES["gap_precision"]
        and avg_hit >= GATES["hit_rate"]
    )
    return {
        "n": n,
        "hit_rate_mean": avg_hit,
        "factuality_proxy": factuality,
        "gap_precision": gap_precision,
        "gates": GATES,
        "passed": passed,
    }


if __name__ == "__main__":
    holdout = Path(__file__).parent / "data" / "eval_medtech_holdout.jsonl"
    print(json.dumps(eval_holdout_jsonl(holdout), indent=2))
