from __future__ import annotations

import structlog

from card_retrieval.adapters.kasikorn.constants import (
    BANK_NAME,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
    SELECTORS,
)
from card_retrieval.adapters.kasikorn.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.stealth_fetcher import StealthFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("kasikorn")
class KasikornAdapter(BaseAdapter):
    def __init__(self):
        self._fetcher = StealthFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("kasikornbank.com", RATE_LIMIT_SECONDS)

        html = await self._fetcher.fetch_rendered_html(
            url=PROMOTION_URL,
            wait_selector=SELECTORS["title"],
            scroll=True,
        )

        promotions = parse_promotions_from_html(html)

        # Deduplicate
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("kasikorn_total_promotions", count=len(unique))
        return unique

    async def close(self):
        await self._fetcher.close()
