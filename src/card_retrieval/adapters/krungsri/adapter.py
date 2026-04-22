from __future__ import annotations

import structlog

from card_retrieval.adapters.krungsri.constants import (
    BANK_NAME,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.krungsri.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.http_fetcher import HttpFetcher

# NB: register the adapter at import time; avoid heavy imports at module scope.
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("krungsri")
class KrungsriAdapter(BaseAdapter):
    """Bank of Ayudhya (Krungsri) credit-card promotion adapter.

    The site serves a static HTML listing at PROMOTION_URL. If Krungsri flips to a
    heavy SPA or starts bot-blocking plain httpx, swap the fetcher here for
    BrowserFetcher or StealthFetcher — the parser is fetcher-agnostic.
    """

    def __init__(self) -> None:
        self._fetcher = HttpFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("krungsri.com", RATE_LIMIT_SECONDS)
        html = await self._fetcher.fetch(PROMOTION_URL)
        promotions = parse_promotions_from_html(html)

        # Deduplicate by source_id in case the grid reuses cards across categories.
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("krungsri_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
