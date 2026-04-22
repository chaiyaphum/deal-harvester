from __future__ import annotations

import structlog

from card_retrieval.adapters.amex.constants import (
    BANK_NAME,
    PRE_VISIT_URL,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
    SELECTORS,
)
from card_retrieval.adapters.amex.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.stealth_fetcher import StealthFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("amex")
class AmexAdapter(BaseAdapter):
    """American Express Thailand promotion adapter.

    Amex hosts public card-member offers under `/th-th/benefits/promotions/`.
    The hub is protected by Akamai Bot Manager — plain httpx gets a
    RemoteProtocolError (TLS stream reset) and BrowserFetcher without a
    warm-up hits a 30 s navigation timeout. `StealthFetcher` with a
    `pre_visit_url` to the TH root succeeds: the root sets the `_abck` /
    `bm_sz` cookies, and the subsequent navigation to the promotions page
    passes the bot check. Verified 2026-04-22: 45 offers rendered on
    `/th-th/benefits/promotions/dining.html`.

    The MVP scrapes the dining category only (largest catalog, cleanest
    DOM). Extending to travel / lifestyle / explore-asia is a matter of
    iterating over those category URLs in `fetch_promotions` — tracked in
    PLAN.md.
    """

    def __init__(self) -> None:
        self._fetcher = StealthFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("americanexpress.com", RATE_LIMIT_SECONDS)

        html = await self._fetcher.fetch_rendered_html(
            url=PROMOTION_URL,
            pre_visit_url=PRE_VISIT_URL,
            wait_selector=SELECTORS["promotion_card"],
            scroll=True,
        )

        promotions = parse_promotions_from_html(html)

        # Deduplicate by source_id.
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("amex_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
