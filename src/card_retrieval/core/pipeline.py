from __future__ import annotations

from datetime import datetime

import structlog

from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import ScrapeRun
from card_retrieval.core.registry import get_adapter, list_adapters
from card_retrieval.storage.repository import PromotionRepository

logger = structlog.get_logger()


async def run_adapter(adapter: BaseAdapter, repo: PromotionRepository) -> ScrapeRun:
    bank = adapter.get_bank_name()
    run = ScrapeRun(bank=bank)
    log = logger.bind(bank=bank, run_id=run.id)
    log.info("scrape_started")

    try:
        promotions = await adapter.fetch_promotions()
        run.promotions_found = len(promotions)
        log.info("promotions_fetched", count=len(promotions))

        new_count, updated_count = repo.upsert_promotions(promotions)
        run.promotions_new = new_count
        run.promotions_updated = updated_count

        run.status = "success"
        run.finished_at = datetime.utcnow()
        log.info(
            "scrape_finished",
            found=run.promotions_found,
            new=new_count,
            updated=updated_count,
        )
    except Exception as e:
        run.status = "failed"
        run.finished_at = datetime.utcnow()
        run.error_message = str(e)
        log.error("scrape_failed", error=str(e))
    finally:
        await adapter.close()

    repo.save_scrape_run(run)
    return run


async def run_pipeline(
    banks: list[str] | None = None,
    repo: PromotionRepository | None = None,
) -> list[ScrapeRun]:
    if repo is None:
        repo = PromotionRepository()

    if banks is None:
        banks = list(list_adapters().keys())

    results = []
    for bank in banks:
        adapter_cls = get_adapter(bank)
        adapter = adapter_cls()
        run = await run_adapter(adapter, repo)
        results.append(run)

    return results
