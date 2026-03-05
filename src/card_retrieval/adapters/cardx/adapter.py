from __future__ import annotations

import structlog

from card_retrieval.adapters.cardx.constants import (
    API_INTERCEPT_PATTERNS,
    BANK_NAME,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.cardx.parser import parse_intercepted_data
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.browser_fetcher import BrowserFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("cardx")
class CardxAdapter(BaseAdapter):
    def __init__(self):
        self._fetcher = BrowserFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("cardx.co.th", RATE_LIMIT_SECONDS)

        all_captured: list[dict] = []
        for pattern in API_INTERCEPT_PATTERNS:
            try:
                captured = await self._fetcher.fetch_with_intercept(
                    url=PROMOTION_URL,
                    intercept_pattern=pattern,
                    wait_time=8.0,
                )
                all_captured.extend(captured)
            except Exception:
                logger.warning("cardx_intercept_error", pattern=pattern, exc_info=True)

        logger.info("cardx_responses_intercepted", count=len(all_captured))

        promotions = parse_intercepted_data(all_captured)

        # Deduplicate by source_id
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("cardx_total_promotions", count=len(unique))
        return unique

    async def close(self):
        await self._fetcher.close()
