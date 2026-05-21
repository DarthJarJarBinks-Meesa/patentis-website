"""Masked patent supervision (CPC subgroup hide-and-predict loop)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.gap_evaluator import filter_to_training_set, score_prediction
from models.masking_config import MaskingConfig, MaskingStrategy
from models.masking_pipeline import build_masked_record, fetch_patents_for_subgroup
from patentis_platform.db.base import Base
from patentis_platform.db.models import PatentRecord, TechnologyRegion
from patentis_platform.graph.build import ensure_region_for_subclass


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_subgroup(session: AsyncSession, cpc: str, n: int) -> None:
    await ensure_region_for_subclass(session, cpc, vertical="medtech")
    for i in range(n):
        session.add(
            PatentRecord(
                id=uuid.uuid4(),
                external_id=f"t_{cpc}_{i}",
                title=f"Patent {i}",
                abstract="abstract",
                claims_text=f"1. A device for signal {i}.\n2. The device of claim 1, wireless.",
                cpc_subclass=cpc,
                cpc_codes=[cpc, "A61B"],
                filing_date=date(2020, 1, 1 + min(i, 27)),
            )
        )
    await session.commit()


@pytest.mark.asyncio
async def test_fetch_subgroup_includes_cpc_codes(db_session: AsyncSession):
    await _seed_subgroup(db_session, "A61B5", 10)
    patents = await fetch_patents_for_subgroup(db_session, "A61B5")
    assert len(patents) == 10


@pytest.mark.asyncio
async def test_build_masked_record_hides_recent(db_session: AsyncSession):
    await _seed_subgroup(db_session, "A61B5", 12)
    cfg = MaskingConfig.development()
    record = await build_masked_record(db_session, "A61B5", cfg)
    assert record is not None
    assert cfg.n_hidden_min <= record["n_hidden"] <= cfg.n_hidden_max
    assert record["n_visible"] >= cfg.min_visible_patents
    assert len(record["hidden_patent_claims"]) == record["n_hidden"]


@pytest.mark.asyncio
async def test_gap_evaluator_hit_rate():
    cfg = MaskingConfig(score_threshold=0.25)
    record = {
        "completion": {
            "gap_description": "wireless implant strain sensing",
            "predicted_claim_space": "micromotion telemetry",
            "suggested_directions": ["RF sensing"],
        },
        "hidden_patent_claims": ["1. A wireless strain sensor for implant micromotion."],
    }
    result = score_prediction(record, cfg)
    assert result["n_hidden"] == 1
    assert "hit_rate" in result


@pytest.mark.asyncio
async def test_temporal_strategy_orders_hidden_last(db_session: AsyncSession):
    await _seed_subgroup(db_session, "A61N1", 15)
    cfg = MaskingConfig.development()
    cfg.strategy = MaskingStrategy.TEMPORAL
    record = await build_masked_record(db_session, "A61N1", cfg)
    assert record is not None
    accepted, rejected = filter_to_training_set([record], [score_prediction(record, cfg)], 0.0)
    assert len(accepted) + len(rejected) == 1
