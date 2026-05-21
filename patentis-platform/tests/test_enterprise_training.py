"""Enterprise training isolation: base SFT vs org LoRA."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.dataset_builder import export_base_sft_jsonl
from patentis_platform.db.base import Base
from patentis_platform.db.models import InteractionSignal, Organization, OrgLoRAAdapter
from patentis_platform.enterprise.opt_out import apply_training_opt_out, purge_due_org_training_data
from patentis_platform.enterprise.org_adapters import resolve_inference_adapter
from patentis_platform.enterprise.training_policy import (
    assert_base_dataset_source,
    FORBIDDEN_BASE_SFT_SOURCES,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_forbidden_base_sources():
    with pytest.raises(ValueError, match="cannot be used for base"):
        assert_base_dataset_source("interaction_signals")
    assert_base_dataset_source("masking_run_records")
    assert "interaction_signals" in FORBIDDEN_BASE_SFT_SOURCES


@pytest.mark.asyncio
async def test_export_briefs_blocked():
    from models import dataset_builder

    with pytest.raises(RuntimeError, match="opportunity_briefs cannot"):
        await dataset_builder.export_briefs_jsonl(None, None)  # type: ignore


@pytest.mark.asyncio
async def test_opt_out_schedules_purge(db_session: AsyncSession):
    org = Organization(id=uuid.uuid4(), name="Acme", training_opt_in=True)
    db_session.add(org)
    db_session.add(
        OrgLoRAAdapter(
            id=uuid.uuid4(),
            org_id=org.id,
            status="active",
            blob_path="org-adapters/test/lora-latest/",
            version="20260101",
        )
    )
    db_session.add(
        InteractionSignal(
            id=uuid.uuid4(),
            org_id=org.id,
            signal_type="test",
            payload_json={"x": 1},
        )
    )
    await db_session.commit()

    result = await apply_training_opt_out(db_session, org.id)
    assert result["training_opt_in"] is False
    assert result["retention_days"] == 30

    inference = await resolve_inference_adapter(db_session, org.id)
    assert inference["uses_customer_adapter"] is False

    org.training_data_purge_after = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()
    purge = await purge_due_org_training_data(db_session)
    assert purge["orgs_purged"] >= 1
    assert purge["logs_deleted"] >= 1
