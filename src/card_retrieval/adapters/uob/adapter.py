from __future__ import annotations

import structlog

from card_retrieval.adapters.uob.constants import (
    BANK_NAME,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.uob.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.http_fetcher import HttpFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("uob")
class UobAdapter(BaseAdapter):
    """UOB Thailand credit-card promotion adapter.

    The hub (`/personal/promotions/creditcard/all-promotion.page`) is a
    server-rendered AEM page. A plain httpx GET with the default Chrome UA
    follows the 301 to the canonical hub and returns the fully populated HTML
    — no JS rendering needed. If UOB ever fronts the hub with Cloudflare or
    changes the wrapper selector, switch to BrowserFetcher and update
    `constants.SELECTORS`; the parser is fetcher-agnostic.
    """

    def __init__(self) -> None:
        self._fetcher = HttpFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("uob.co.th", RATE_LIMIT_SECONDS)
        html = await self._fetcher.fetch(PROMOTION_URL)
        promotions = parse_promotions_from_html(html)

        # Deduplicate by source_id (UOB occasionally features the same promo
        # in multiple category carousels, though the current hub doesn't).
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("uob_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
