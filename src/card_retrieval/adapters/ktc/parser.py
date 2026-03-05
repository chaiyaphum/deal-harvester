from __future__ import annotations

import json
from datetime import date, datetime

import structlog
from bs4 import BeautifulSoup

from card_retrieval.adapters.ktc.constants import BASE_URL, BANK_NAME
from card_retrieval.core.models import Promotion
from card_retrieval.utils.text import extract_discount, normalize_thai_text

logger = structlog.get_logger()


def extract_next_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ JSON from the page."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            logger.warning("ktc_next_data_parse_error")
    return None


def parse_promotions_from_next_data(data: dict) -> list[Promotion]:
    """Parse promotions from __NEXT_DATA__ JSON structure."""
    promotions: list[Promotion] = []

    # Navigate the typical Next.js page props structure
    page_props = data.get("props", {}).get("pageProps", {})

    # Try common data locations in Next.js apps
    promo_list = (
        page_props.get("promotions")
        or page_props.get("data", {}).get("promotions")
        or page_props.get("initialData", {}).get("promotions")
        or page_props.get("items")
        or []
    )

    if not promo_list and isinstance(page_props, dict):
        # Search for any list of items that looks like promotions
        for key, value in page_props.items():
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                if any(k in value[0] for k in ("title", "name", "slug", "id")):
                    promo_list = value
                    logger.info("ktc_found_promos_in_key", key=key, count=len(value))
                    break

    for item in promo_list:
        promo = _parse_single_promotion(item)
        if promo:
            promotions.append(promo)

    return promotions


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Fallback: parse promotions directly from HTML if __NEXT_DATA__ is missing."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    # Look for common promotion card patterns
    cards = soup.select(
        "a[href*='/promotion/'], "
        "div[class*='promotion'], "
        "div[class*='card-item'], "
        "div[class*='PromoCard']"
    )

    for card in cards:
        try:
            link = card.get("href") or ""
            if isinstance(card, BeautifulSoup) or card.name != "a":
                a_tag = card.find("a", href=True)
                link = a_tag["href"] if a_tag else ""

            title_el = card.find(["h2", "h3", "h4", "p"])
            title = normalize_thai_text(title_el.get_text()) if title_el else ""
            if not title:
                continue

            img = card.find("img")
            image_url = img.get("src") or img.get("data-src") if img else None
            if image_url and image_url.startswith("/"):
                image_url = BASE_URL + image_url

            source_url = link if link.startswith("http") else BASE_URL + link
            source_id = link.rstrip("/").split("/")[-1] if link else title[:50]

            promotions.append(
                Promotion(
                    bank=BANK_NAME,
                    source_id=source_id,
                    source_url=source_url,
                    title=title,
                    image_url=image_url,
                    raw_data={"html_source": True},
                )
            )
        except Exception:
            logger.debug("ktc_html_card_parse_error", exc_info=True)

    return promotions


def _parse_single_promotion(item: dict) -> Promotion | None:
    """Parse a single promotion item from JSON data."""
    try:
        source_id = str(item.get("id") or item.get("slug") or item.get("_id", ""))
        title = item.get("title") or item.get("name") or ""
        if not source_id or not title:
            return None

        slug = item.get("slug", source_id)
        source_url = f"{BASE_URL}/promotion/{slug}"

        description = item.get("description") or item.get("short_description") or ""
        description = normalize_thai_text(description)

        image_url = item.get("image") or item.get("thumbnail") or item.get("cover_image")
        if isinstance(image_url, dict):
            image_url = image_url.get("url") or image_url.get("src")
        if image_url and image_url.startswith("/"):
            image_url = BASE_URL + image_url

        category = item.get("category") or item.get("type")
        if isinstance(category, dict):
            category = category.get("name") or category.get("slug")

        card_types = item.get("card_types") or item.get("cards") or []
        if isinstance(card_types, str):
            card_types = [card_types]
        elif isinstance(card_types, list):
            card_types = [
                ct.get("name", str(ct)) if isinstance(ct, dict) else str(ct) for ct in card_types
            ]

        start_date = _parse_date(item.get("start_date") or item.get("startDate"))
        end_date = _parse_date(item.get("end_date") or item.get("endDate"))

        discount_type, discount_value = extract_discount(title + " " + description)

        return Promotion(
            bank=BANK_NAME,
            source_id=source_id,
            source_url=source_url,
            title=normalize_thai_text(title),
            description=description,
            image_url=image_url,
            card_types=card_types,
            category=str(category) if category else None,
            discount_type=discount_type,
            discount_value=discount_value,
            start_date=start_date,
            end_date=end_date,
            raw_data=item,
        )
    except Exception:
        logger.debug("ktc_promotion_parse_error", item_id=item.get("id"), exc_info=True)
        return None


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None
