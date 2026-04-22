from __future__ import annotations

import structlog

from card_retrieval.adapters.bbl.constants import (
    BANK_NAME,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.bbl.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.browser_fetcher import BrowserFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("bbl")
class BblAdapter(BaseAdapter):
    """Bangkok Bank (BBL) credit-card promotion adapter.

    BBL runs on Sitecore (ASP.NET). The TH locale at
    `/th/personal/other-services/promotions/credit-card-promotions` 404s and
    the `/th` landing page itself returns a 500 as of 2026-04-22 — BBL's
    Thai Sitecore instance is broken. The EN hub at
    `/en/Personal/Cards/Credit-Cards/Promotions` renders cleanly and we
    scrape that; `PROMOTION_URL` will flip back to TH once BBL repairs it
    (selectors are identical — Sitecore renders the same component for both
    locales).

    Plain httpx / curl fail with a TLS stream reset (BBL does TLS/JA3
    fingerprint matching on direct clients). Playwright's Chromium bundle
    presents a real Chrome TLS handshake and passes. No anti-bot challenge
    observed beyond the TLS gate.
    """

    def __init__(self) -> None:
        self._fetcher = BrowserFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        await rate_limiter.wait("bangkokbank.com", RATE_LIMIT_SECONDS)

        # The promo tiles hydrate after `networkidle` — fetch without a
        # wait_selector because `divCardPromotionsListing` is already in the
        # SSR HTML; inner `.thumb-default` children populate during hydration.
        html = await self._fetcher.fetch_rendered_html(
            url=PROMOTION_URL,
            wait_selector=None,
        )

        promotions = parse_promotions_from_html(html)

        # Deduplicate by source_id.
        seen: set[str] = set()
        unique: list[Promotion] = []
        for p in promotions:
            if p.source_id not in seen:
                seen.add(p.source_id)
                unique.append(p)

        logger.info("bbl_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
