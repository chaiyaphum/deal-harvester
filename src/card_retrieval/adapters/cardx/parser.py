from __future__ import annotations

from datetime import date, datetime

import structlog

from card_retrieval.adapters.cardx.constants import BANK_NAME, BASE_URL
from card_retrieval.core.models import Promotion
from card_retrieval.utils.text import extract_discount, normalize_thai_text

logger = structlog.get_logger()


def parse_intercepted_data(responses: list[dict]) -> list[Promotion]:
    """Parse promotions from intercepted API responses."""
    promotions: list[Promotion] = []

    for response_data in responses:
        items = _extract_items(response_data)
        for item in items:
            promo = _parse_item(item)
            if promo:
                promotions.append(promo)

    return promotions


def _extract_items(data: dict) -> list[dict]:
    """Navigate various API response formats to find promotion items."""
    # Direct list
    if isinstance(data, list):
        return data

    # Common wrapper patterns
    for key in ("data", "results", "items", "promotions", "content"):
        if key in data:
            val = data[key]
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                # Nested: data.items, data.promotions, etc.
                for inner_key in ("items", "promotions", "results", "edges", "nodes"):
                    if inner_key in val and isinstance(val[inner_key], list):
                        return val[inner_key]

    # GraphQL pattern
    if "data" in data and isinstance(data["data"], dict):
        for value in data["data"].values():
            if isinstance(value, dict) and "edges" in value:
                return [edge.get("node", edge) for edge in value["edges"]]
            if isinstance(value, list):
                return value

    return []


def _parse_item(item: dict) -> Promotion | None:
    try:
        source_id = str(item.get("id") or item.get("promotionId") or item.get("slug") or "")
        title = item.get("title") or item.get("name") or item.get("promotionName") or ""
        if not source_id or not title:
            return None

        slug = item.get("slug") or item.get("urlSlug") or source_id
        source_url = f"{BASE_URL}/credit-card/promotion/{slug}"

        description = item.get("description") or item.get("shortDescription") or ""
        description = normalize_thai_text(str(description))

        image_url = (
            item.get("image")
            or item.get("imageUrl")
            or item.get("thumbnail")
            or item.get("coverImage")
        )
        if isinstance(image_url, dict):
            image_url = image_url.get("url") or image_url.get("src")

        category = item.get("category") or item.get("categoryName")
        if isinstance(category, dict):
            category = category.get("name") or category.get("slug")

        card_types = item.get("cardTypes") or item.get("cards") or []
        if isinstance(card_types, str):
            card_types = [card_types]
        elif isinstance(card_types, list):
            card_types = [
                ct.get("name", str(ct)) if isinstance(ct, dict) else str(ct) for ct in card_types
            ]

        start_date = _parse_date(item.get("startDate") or item.get("start_date"))
        end_date = _parse_date(item.get("endDate") or item.get("end_date"))

        merchant = item.get("merchantName") or item.get("merchant")
        if isinstance(merchant, dict):
            merchant = merchant.get("name")

        discount_type, discount_value = extract_discount(title + " " + description)

        return Promotion(
            bank=BANK_NAME,
            source_id=source_id,
            source_url=source_url,
            title=normalize_thai_text(str(title)),
            description=description,
            image_url=image_url,
            card_types=card_types,
            category=str(category) if category else None,
            merchant_name=str(merchant) if merchant else None,
            discount_type=discount_type,
            discount_value=discount_value,
            start_date=start_date,
            end_date=end_date,
            raw_data=item,
        )
    except Exception:
        logger.debug("cardx_item_parse_error", exc_info=True)
        return None


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000).date()
        except (ValueError, OSError):
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None
