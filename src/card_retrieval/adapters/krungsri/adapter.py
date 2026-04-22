from __future__ import annotations

import structlog

from card_retrieval.adapters.krungsri.constants import (
    BANK_NAME,
    BASE_URL,
    CATEGORY_SLUGS,
    PRE_VISIT_URL,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.krungsri.parser import parse_promotions_from_html
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.stealth_fetcher import StealthFetcher

# NB: register the adapter at import time; avoid heavy imports at module scope.
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()

# Hub slug → Promotion.category mapping. Applied at adapter level so the parser
# stays fetcher-agnostic and hub-agnostic.
CATEGORY_MAP: dict[str, str] = {
    "hot-promotion": "featured",
    "dining": "dining",
    "shopping-online": "shopping",
    "travel": "travel",
}


@register("krungsri")
class KrungsriAdapter(BaseAdapter):
    """Bank of Ayudhya (Krungsri) credit-card promotion adapter.

    Krungsri's promo hub lives at `/th/promotions/cards/{slug}` and is
    protected by Imperva/Incapsula — plain httpx returns a 958-byte
    challenge page. We use `StealthFetcher` with a pre-visit to `/th/` to
    seed the bot cookies, then iterate the category sub-pages (each serves
    only 1-6 tiles on its own, so we walk all four to get meaningful
    coverage).
    """

    def __init__(self) -> None:
        self._fetcher = StealthFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        seen: set[str] = set()
        unique: list[Promotion] = []

        for slug in CATEGORY_SLUGS:
            url = f"{BASE_URL}/th/promotions/cards/{slug}"
            await rate_limiter.wait("krungsri.com", RATE_LIMIT_SECONDS)
            try:
                # Pre-visit is only needed on the first fetch — subsequent
                # calls reuse the warm Incapsula context inside the same
                # Playwright browser session. Passing it every time is safe
                # (fetcher re-navigates) but slower; we only warm once.
                html = await self._fetcher.fetch_rendered_html(
                    url=url,
                    pre_visit_url=PRE_VISIT_URL if not seen else None,
                    scroll=True,
                )
            except Exception:
                logger.warning("krungsri_hub_fetch_failed", slug=slug, exc_info=True)
                continue

            hub_category = CATEGORY_MAP.get(slug)
            hub_promos = parse_promotions_from_html(html)
            for p in hub_promos:
                if p.source_id in seen:
                    continue
                seen.add(p.source_id)
                # Stamp the hub-level category when the listing did not
                # expose an inline category element.
                if hub_category and not p.category:
                    p.category = hub_category
                unique.append(p)

        logger.info("krungsri_total_promotions", count=len(unique))
        return unique

    async def close(self) -> None:
        await self._fetcher.close()
