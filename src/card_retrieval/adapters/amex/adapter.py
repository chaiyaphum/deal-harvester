from __future__ import annotations

import structlog

from card_retrieval.adapters.amex.constants import (
    BANK_NAME,
    HUB_CATEGORY_MAP,
    PRE_VISIT_URL,
    PROMOTION_HUBS,
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

    Amex hosts public card-member offers under four category hubs at
    `/th-th/benefits/promotions/{dining,travel,lifestyle,explore-asia}.html`.
    All four use the same AEM template (`div.offer.parbase`) so the adapter
    iterates them and stamps `Promotion.category` per hub via
    `HUB_CATEGORY_MAP`.

    The hub set is protected by Akamai Bot Manager — plain httpx gets a
    RemoteProtocolError (TLS stream reset) and BrowserFetcher without a
    warm-up hits a 30 s navigation timeout. `StealthFetcher` with a single
    pre-visit to the TH root succeeds: the root sets the `_abck` / `bm_sz`
    cookies, and every subsequent navigation (all four hubs) reuses that
    warm session. Verified 2026-04-22:
        dining       → 45 tiles
        lifestyle    → 20 tiles
        travel       → 13 tiles
        explore-asia →  8 tiles
    """

    def __init__(self) -> None:
        self._fetcher = StealthFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        # Canonical URL for the adapter. The iteration inside
        # `fetch_promotions` visits all hubs.
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        seen: set[str] = set()
        unique: list[Promotion] = []

        for i, (hub_slug, url) in enumerate(PROMOTION_HUBS):
            # Rate-limit between every hub fetch (Akamai tracks velocity per
            # source IP). The first fetch also performs the pre-visit warm-up;
            # subsequent fetches reuse the warm Akamai context inside the same
            # Playwright browser session.
            await rate_limiter.wait("americanexpress.com", RATE_LIMIT_SECONDS)

            pre_visit = PRE_VISIT_URL if i == 0 else None
            try:
                html = await self._fetcher.fetch_rendered_html(
                    url=url,
                    pre_visit_url=pre_visit,
                    wait_selector=SELECTORS["promotion_card"],
                    scroll=True,
                )
            except Exception:
                logger.warning("amex_hub_fetch_failed", hub=hub_slug, exc_info=True)
                continue

            category = HUB_CATEGORY_MAP.get(hub_slug, hub_slug)
            hub_promos = parse_promotions_from_html(html, category=category, hub_url=url)
            logger.info("amex_hub_parsed", hub=hub_slug, count=len(hub_promos))

            for p in hub_promos:
                if p.source_id in seen:
                    continue
                seen.add(p.source_id)
                unique.append(p)

        logger.info("amex_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
