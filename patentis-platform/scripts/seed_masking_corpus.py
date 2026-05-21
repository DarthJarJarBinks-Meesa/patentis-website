"""
Seed enough patents with claims in one CPC subgroup for masked supervision (dev / demo).

  MASKING_DEV_MODE=true python scripts/seed_masking_corpus.py
  # or production-sized corpus:
  python scripts/seed_masking_corpus.py --count 45 --cpc A61B5
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date, timedelta

from patentis_platform.db.session import get_session_factory
from patentis_platform.graph.build import ensure_region_for_subclass
from patentis_platform.db.models import PatentRecord

CLAIM_TEMPLATES = [
    "1. A medical device comprising a sensor configured to measure {signal} in an implant.",
    "2. The device of claim 1, wherein the sensor communicates via wireless telemetry.",
    "3. A method of monitoring {signal} comprising attaching the device of claim 1 to bone.",
]


async def seed(cpc: str, count: int, vertical: str) -> int:
    factory = get_session_factory()
    async with factory() as session:
        await ensure_region_for_subclass(session, cpc, vertical=vertical)
        base = date.today() - timedelta(days=count * 30)
        n = 0
        for i in range(count):
            signal = ["micromotion", "strain", "pressure", "temperature"][i % 4]
            claims = "\n\n".join(t.format(signal=signal) for t in CLAIM_TEMPLATES)
            ext = f"maskseed_{cpc}_{i:04d}"
            session.add(
                PatentRecord(
                    id=uuid.uuid4(),
                    external_id=ext,
                    title=f"Masking seed patent {i} for {cpc} — {signal} sensing",
                    abstract=f"Abstract describing {signal} sensing in CPC {cpc}.",
                    claims_text=claims,
                    cpc_subclass=cpc,
                    cpc_codes=[cpc, cpc[:4]],
                    filing_date=base + timedelta(days=i * 25),
                    assignee=f"Seed Assignee {i % 7}",
                    source="masking_seed",
                )
            )
            n += 1
        await session.commit()
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cpc", default="A61B5")
    p.add_argument("--count", type=int, default=45)
    p.add_argument("--vertical", default="medtech")
    args = p.parse_args()
    n = asyncio.run(seed(args.cpc, args.count, args.vertical))
    print(f"Seeded {n} patents with claims for subgroup {args.cpc}")


if __name__ == "__main__":
    main()
