from __future__ import annotations

from datetime import datetime

import structlog

from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import ScrapeRun
from card_retrieval.core.registry import get_adapter, list_adapters
from card_retrieval.storage.repository import PromotionRepository

logger = structlog.get_logger()

REPEATED_FAILURE_THRESHOLD = 3


async def run_adapter(
    adapter: BaseAdapter,
    repo: PromotionRepository,
    dry_run: bool = False,
) -> ScrapeRun:
    bank = adapter.get_bank_name()
    run = ScrapeRun(bank=bank)
    log = logger.bind(bank=bank, run_id=run.id)
    log.info("scrape_started")

    try:
        promotions = await adapter.fetch_promotions()
        run.promotions_found = len(promotions)
        log.info("promotions_fetched", count=len(promotions))

        if dry_run:
            log.info("dry_run_skip_db", found=len(promotions))
            run.promotions_new = 0
            run.promotions_updated = 0
        else:
            new_count, updated_count = repo.upsert_promotions(promotions)
            run.promotions_new = new_count
            run.promotions_updated = updated_count

            # Soft-delete promotions that are no longer on the site
            if promotions:
                active_source_ids = [p.source_id for p in promotions]
                deactivated = repo.deactivate_missing(bank, active_source_ids)
                if deactivated:
                    log.info("promotions_deactivated", count=deactivated)

        run.status = "success"
        run.finished_at = datetime.utcnow()
        log.info(
            "scrape_finished",
            found=run.promotions_found,
            new=run.promotions_new,
            updated=run.promotions_updated,
        )
    except Exception as e:
        run.status = "failed"
        run.finished_at = datetime.utcnow()
        run.error_message = str(e)
        log.error("scrape_failed", error=str(e))
    finally:
        await adapter.close()

    if not dry_run:
        repo.save_scrape_run(run)

        # Check for repeated failures
        if run.status == "failed":
            _check_repeated_failures(repo, bank, log)

    return run


def _check_repeated_failures(
    repo: PromotionRepository,
    bank: str,
    log: structlog.stdlib.BoundLogger,
) -> None:
    recent_runs = repo.get_scrape_runs(bank=bank, limit=REPEATED_FAILURE_THRESHOLD)
    if len(recent_runs) >= REPEATED_FAILURE_THRESHOLD and all(
        r.status == "failed" for r in recent_runs
    ):
        log.critical(
            "adapter_repeated_failure",
            consecutive_failures=len(recent_runs),
            last_error=recent_runs[0].error_message,
        )


async def run_pipeline(
    banks: list[str] | None = None,
    repo: PromotionRepository | None = None,
    dry_run: bool = False,
) -> list[ScrapeRun]:
    if repo is None:
        repo = PromotionRepository()

    if banks is None:
        banks = list(list_adapters().keys())

    results = []
    for bank in banks:
        adapter_cls = get_adapter(bank)
        adapter = adapter_cls()
        run = await run_adapter(adapter, repo, dry_run=dry_run)
        results.append(run)

    return results
