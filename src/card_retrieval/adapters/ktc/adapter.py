from __future__ import annotations

import structlog

from card_retrieval.adapters.ktc.constants import (
    BANK_NAME,
    CATEGORIES,
    PROMOTION_URL,
    RATE_LIMIT_SECONDS,
)
from card_retrieval.adapters.ktc.parser import (
    extract_next_data,
    parse_promotions_from_html,
    parse_promotions_from_next_data,
)
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register
from card_retrieval.fetchers.http_fetcher import HttpFetcher
from card_retrieval.utils.rate_limiter import rate_limiter

logger = structlog.get_logger()


@register("ktc")
class KtcAdapter(BaseAdapter):
    def __init__(self):
        self._fetcher = HttpFetcher()

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        all_promotions: list[Promotion] = []
        seen_ids: set[str] = set()

        # Fetch main promotion page
        await rate_limiter.wait("ktc.co.th", RATE_LIMIT_SECONDS)
        html = await self._fetcher.fetch(PROMOTION_URL)

        next_data = extract_next_data(html)
        if next_data:
            promos = parse_promotions_from_next_data(next_data)
            logger.info("ktc_main_page_parsed", method="next_data", count=len(promos))
        else:
            promos = parse_promotions_from_html(html)
            logger.info("ktc_main_page_parsed", method="html_fallback", count=len(promos))

        for p in promos:
            if p.source_id not in seen_ids:
                seen_ids.add(p.source_id)
                all_promotions.append(p)

        # Fetch category pages
        for category in CATEGORIES:
            try:
                url = f"{PROMOTION_URL}/{category}"
                await rate_limiter.wait("ktc.co.th", RATE_LIMIT_SECONDS)
                cat_html = await self._fetcher.fetch(url)

                cat_data = extract_next_data(cat_html)
                if cat_data:
                    cat_promos = parse_promotions_from_next_data(cat_data)
                else:
                    cat_promos = parse_promotions_from_html(cat_html)

                new_count = 0
                for p in cat_promos:
                    if p.source_id not in seen_ids:
                        seen_ids.add(p.source_id)
                        if not p.category:
                            p.category = category
                        all_promotions.append(p)
                        new_count += 1

                if new_count:
                    logger.info("ktc_category_parsed", category=category, new=new_count)
            except Exception:
                logger.warning("ktc_category_error", category=category, exc_info=True)

        logger.info("ktc_total_promotions", count=len(all_promotions))
        return all_promotions

    async def close(self):
        await self._fetcher.close()
