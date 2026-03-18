from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from card_retrieval.config import settings
from card_retrieval.core.pipeline import run_pipeline

logger = structlog.get_logger()


def _run_bank(bank: str):
    """Wrapper to run a single bank adapter in the scheduler."""

    async def _job():
        logger.info("scheduled_run_start", bank=bank)
        results = await run_pipeline(banks=[bank])
        for r in results:
            logger.info(
                "scheduled_run_complete",
                bank=r.bank,
                status=r.status,
                found=r.promotions_found,
            )

    asyncio.get_running_loop().create_task(_job())


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        lambda: _run_bank("ktc"),
        "interval",
        hours=settings.schedule_ktc,
        id="ktc_scrape",
        name="KTC Promotion Scrape",
    )
    scheduler.add_job(
        lambda: _run_bank("cardx"),
        "interval",
        hours=settings.schedule_cardx,
        id="cardx_scrape",
        name="CardX Promotion Scrape",
    )
    scheduler.add_job(
        lambda: _run_bank("kasikorn"),
        "interval",
        hours=settings.schedule_kasikorn,
        id="kasikorn_scrape",
        name="Kasikorn Promotion Scrape",
    )

    return scheduler
