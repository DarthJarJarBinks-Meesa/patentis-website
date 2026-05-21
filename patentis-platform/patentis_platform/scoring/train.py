"""CLI: train whitespace models from DB regions."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from typing import Optional

from sqlalchemy import select

from patentis_platform.db.models import TechnologyRegion
from patentis_platform.db.session import get_session_factory
from patentis_platform.scoring.models_ml import train_and_save
from patentis_platform.scoring.org_labels import fetch_org_region_labels


async def async_main(vertical: str, org_id: Optional[uuid.UUID]):
    fac = get_session_factory()
    async with fac() as session:
        res = await session.execute(
            select(TechnologyRegion).where(TechnologyRegion.vertical == vertical)
        )
        regions = list(res.scalars().all())
        labels: dict[uuid.UUID, float] = {}
        if org_id:
            labels = await fetch_org_region_labels(session, org_id)

    if len(regions) < 2:
        print("Not enough regions — run python -m patentis_platform.ingestion.seed_medtech first")
        return

    for r in regions:
        lid = labels.get(r.id)
        if lid is not None:
            r.expert_calibration_label = lid

    out = train_and_save(regions, org_id=str(org_id) if org_id else None)

    if org_id:
        print(
            "Saved org-specific scoring artifact (IsolationForest + RF). "
            "Global TechnologyRegion rows were not modified — other tenants unaffected."
        )
        print(out)
        return

    fac = get_session_factory()
    async with fac() as session:
        ids_scores = zip([r.id for r in regions], out["scores"])
        for rid, scores in ids_scores:
            obj = await session.get(TechnologyRegion, rid)
            if not obj:
                continue
            obj.isolation_forest_score = scores["if"]
            obj.rf_opportunity_score = scores["rf"]
            obj.composite_whitespace_score = scores["composite"]
        await session.commit()
    print(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default="medtech")
    parser.add_argument(
        "--org-id",
        default=None,
        help="Train RF targets from this organization's expert_ratings only; write artifact whitespace_models_org_<id>.joblib without updating shared region scores.",
    )
    args = parser.parse_args()
    oid = uuid.UUID(args.org_id) if args.org_id else None
    asyncio.run(async_main(args.vertical, oid))


if __name__ == "__main__":
    main()
