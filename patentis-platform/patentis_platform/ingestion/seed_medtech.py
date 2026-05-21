"""
Seed medtech CPC regions + synthetic patents for offline development when APIs fail.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import PatentRecord, TechnologyRegion


MEDTECH_SEED_REGIONS = [
    {
        "cpc_subclass": "A61B",
        "patent_count": 12000,
        "neighbor_avg_count": 15000,
        "assignee_hhi": 0.02,
        "top_assignee_share": 0.08,
        "filing_growth_rate": 0.12,
        "citation_acceleration": 0.05,
        "pubmed_velocity": 0.4,
        "semantic_sparsity": 0.35,
    },
    {
        "cpc_subclass": "A61F",
        "patent_count": 4800,
        "neighbor_avg_count": 9000,
        "assignee_hhi": 0.04,
        "top_assignee_share": 0.11,
        "filing_growth_rate": 0.18,
        "citation_acceleration": 0.09,
        "pubmed_velocity": 0.25,
        "semantic_sparsity": 0.55,
    },
    {
        "cpc_subclass": "A61N",
        "patent_count": 3200,
        "neighbor_avg_count": 7500,
        "assignee_hhi": 0.06,
        "top_assignee_share": 0.14,
        "filing_growth_rate": 0.22,
        "citation_acceleration": 0.07,
        "pubmed_velocity": 0.32,
        "semantic_sparsity": 0.48,
    },
    {
        "cpc_subclass": "A61B5",
        "patent_count": 900,
        "neighbor_avg_count": 2200,
        "assignee_hhi": 0.09,
        "top_assignee_share": 0.19,
        "filing_growth_rate": 0.31,
        "citation_acceleration": 0.14,
        "pubmed_velocity": 0.55,
        "semantic_sparsity": 0.62,
    },
]

SAMPLE_PATENTS = [
    (
        "US-SEED-1001",
        "Wearable hemodynamic monitoring with multi-modal fusion",
        "A system comprising sensors for PPG and impedance cardiography fused with machine learning.",
        "A61B",
        "Acme Medtech",
    ),
    (
        "US-SEED-1002",
        "Implant sensor for micromotion detection in joint prostheses",
        "Capacitive strain sensing elements configured to detect micromotion between implant and bone.",
        "A61F",
        "OrthoCorp",
    ),
    (
        "US-SEED-1003",
        "Closed-loop neuromodulation based on biomarker feedback",
        "A neurostimulator adjusting therapy parameters using biomarker estimates from local field potentials.",
        "A61N",
        "NeuroPulse Inc",
    ),
]


def _compute_component_scores(r: dict) -> tuple[float, float, float]:
    """Derive normalized component scores from raw features (0-1 scale)."""
    density = r["patent_count"] / max(r["neighbor_avg_count"], 1.0)
    scarcity = max(0.0, min(1.0, 1.0 - density + 0.5 * r["semantic_sparsity"]))
    concentration = max(0.0, min(1.0, 1.0 - r["assignee_hhi"] * 5))
    momentum = max(
        0.0,
        min(
            1.0,
            0.45 * min(r["filing_growth_rate"] * 3, 1.0)
            + 0.35 * min(r["citation_acceleration"] * 5, 1.0)
            + 0.20 * min(r["pubmed_velocity"], 1.0),
        ),
    )
    return scarcity, concentration, momentum


async def seed_regions(session: AsyncSession, vertical: str = "medtech") -> int:
    n = 0
    for row in MEDTECH_SEED_REGIONS:
        cpc = row["cpc_subclass"]
        existing = await session.execute(
            select(TechnologyRegion).where(
                TechnologyRegion.cpc_subclass == cpc,
                TechnologyRegion.vertical == vertical,
            )
        )
        if existing.scalar_one_or_none():
            continue
        sc, co, mo = _compute_component_scores(row)
        session.add(
            TechnologyRegion(
                id=uuid.uuid4(),
                cpc_subclass=cpc,
                vertical=vertical,
                patent_count=row["patent_count"],
                neighbor_avg_count=row["neighbor_avg_count"],
                assignee_hhi=row["assignee_hhi"],
                top_assignee_share=row["top_assignee_share"],
                filing_growth_rate=row["filing_growth_rate"],
                citation_acceleration=row["citation_acceleration"],
                pubmed_velocity=row["pubmed_velocity"],
                semantic_sparsity=row["semantic_sparsity"],
                scarcity_score=sc,
                concentration_score=co,
                momentum_score=mo,
            )
        )
        n += 1
    return n


async def seed_patents(session: AsyncSession) -> int:
    n = 0
    for ext, title, abstract, cpc, assignee in SAMPLE_PATENTS:
        existing = await session.execute(select(PatentRecord).where(PatentRecord.external_id == ext))
        if existing.scalar_one_or_none():
            continue
        session.add(
            PatentRecord(
                id=uuid.uuid4(),
                external_id=ext,
                title=title,
                abstract=abstract,
                cpc_subclass=cpc,
                assignee=assignee,
                filing_date=date(2023, 1, 15 + n),
                source="seed",
                url=f"https://patents.google.com/patent/{ext}/en",
            )
        )
        n += 1
    return n


async def run_seed(vertical: str = "medtech") -> tuple[int, int]:
    from patentis_platform.db.session import get_session_factory

    fac = get_session_factory()
    async with fac() as session:
        a = await seed_regions(session, vertical=vertical)
        b = await seed_patents(session)
        await session.commit()
        return a, b


async def main():
    a, b = await run_seed()
    print(f"Seeded regions: {a}, patents: {b}")


if __name__ == "__main__":
    asyncio.run(main())
