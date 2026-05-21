"""Create extensions and tables. Run: python -m patentis_platform.db.init_db"""

import asyncio

from sqlalchemy import text

from patentis_platform.db.base import Base
from patentis_platform.db.models import (  # noqa: F401 — register models
    AuditLog,
    CorpusDocument,
    DPOFeedback,
    ExpertRating,
    InteractionSignal,
    OpportunityBrief,
    CpcAdjacency,
    MaskingRunRecord,
    OrgRegionScore,
    OrgLoRAAdapter,
    Organization,
    PatentFigure,
    PatentCitation,
    PatentRecord,
    Project,
    TechnologyRegion,
    User,
)
from patentis_platform.db.session import get_engine


async def main() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized (tables + vector extension).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
