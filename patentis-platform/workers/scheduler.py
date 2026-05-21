"""Job scheduler — run via cron or `python -m workers.scheduler <job>`."""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patentis.scheduler")


async def job_masking() -> None:
    from models.auto_trainer import run_nightly_masking_job

    result = await run_nightly_masking_job()
    logger.info("masking job: %s", result)


async def job_scoring() -> None:
    from patentis_platform.agents.orchestrator import refresh_scores_if_models
    from patentis_platform.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        n = await refresh_scores_if_models(session, "medtech")
        logger.info("rescored %s regions", n)


async def job_figures() -> None:
    from patentis_platform.db.session import get_session_factory
    from patentis_platform.multimodal.figure_captioner import caption_active_cpc_patents

    factory = get_session_factory()
    async with factory() as session:
        n = await caption_active_cpc_patents(session, limit=25)
        await session.commit()
        logger.info("captioned %s patents", n)


async def job_neighbors() -> None:
    from patentis_platform.db.session import get_session_factory
    from patentis_platform.graph.queries import refresh_neighbor_avg_counts, seed_cpc_adjacency

    factory = get_session_factory()
    async with factory() as session:
        await seed_cpc_adjacency(session)
        n = await refresh_neighbor_avg_counts(session)
        await session.commit()
        logger.info("neighbor refresh: %s regions", n)


async def job_training_purge() -> None:
    from patentis_platform.db.session import get_session_factory
    from patentis_platform.enterprise.opt_out import purge_due_org_training_data

    factory = get_session_factory()
    async with factory() as session:
        result = await purge_due_org_training_data(session)
        await session.commit()
        logger.info("training purge: %s", result)


JOBS = {
    "masking": job_masking,
    "scoring": job_scoring,
    "figures": job_figures,
    "neighbors": job_neighbors,
    "training-purge": job_training_purge,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=list(JOBS.keys()) + ["all"])
    args = parser.parse_args()

    if args.job == "all":
        for name, fn in JOBS.items():
            logger.info("Running %s", name)
            asyncio.run(fn())
    else:
        asyncio.run(JOBS[args.job]())


if __name__ == "__main__":
    main()
