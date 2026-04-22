from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup, Tag

from card_retrieval.adapters.amex.constants import (
    BANK_NAME,
    BASE_URL,
    PROMOTION_URL,
    SELECTORS,
)
from card_retrieval.core.models import Promotion
from card_retrieval.utils.text import (
    extract_discount,
    extract_minimum_spend,
    normalize_thai_text,
)

logger = structlog.get_logger()


# Reuse the shared Thai preposition merchant heuristic. Amex titles are often
# just the merchant name ("4K คาเฟ่ โรงแรมครอสไวบ์เชียงใหม่ดีเซม") with no "ที่"
# prefix, so we fall back to using the title itself when no pattern matches,
# filtered against a blocklist of Amex brand names.
_MERCHANT_END = (
    r"(?=\s+\d|\s+ตั้งแต่|\s+วันที่|\s+สาขา|\s+เมื่อ|\s+เพียง|"
    r"\s+ทุก|\s+และ|\s+หรือ|\s*$)"
)
_MERCHANT_PATTERNS = [
    re.compile(
        r"ที่\s+("
        r"[A-Z][A-Z0-9\s&.\-']{2,60}"
        r"|[A-Z][a-zA-Z0-9\s&.\-']{2,60}?"
        r"|[฀-๿0-9\s&.\-']{3,60}?"
        r")" + _MERCHANT_END
    ),
    re.compile(
        r"ร่วมกับ\s+("
        r"[A-Z][A-Z0-9\s&.\-']{2,60}"
        r"|[A-Z][a-zA-Z0-9\s&.\-']{2,60}?"
        r"|[฀-๿0-9\s&.\-']{3,60}?"
        r")" + _MERCHANT_END
    ),
]

_MERCHANT_BLOCKLIST = re.compile(
    r"บัตรเครดิต|บัตรเดบิต|อเมริกัน|Amex|American\s*Express|Platinum|"
    r"มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|"
    r"กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม",
    re.IGNORECASE,
)


def _extract_merchant_name(title: str, description: str) -> str | None:
    text = f"{title} {description}".strip()
    for pattern in _MERCHANT_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().rstrip(",.* ")
            if candidate and not _MERCHANT_BLOCKLIST.search(candidate):
                return candidate[:255]

    # Amex title tiles ARE the merchant name ~90% of the time — if the title
    # is short, looks like a brand/venue name, and isn't bank chrome, use it.
    if title and len(title) <= 80 and not _MERCHANT_BLOCKLIST.search(title):
        return title.strip()[:255]
    return None


def _parse_amex_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse Amex's listing date strings.

    Amex ships Western-calendar dates in DD/MM/YYYY, typically prefixed with
    the Thai word "ระยะเวลา:" ("period:"). Example:
        "ระยะเวลา: 01/04/2026 - 30/09/2026"
    Some variants use spaces around slashes or an en-dash.
    """
    # Strip the leading "ระยะเวลา:" prefix if present.
    cleaned = re.sub(r"^\s*ระยะเวลา\s*[:：]?\s*", "", text).strip()
    parts = re.split(r"\s+[-–~]\s+|\s+ถึง\s+", cleaned, maxsplit=1)

    def _try(part: str) -> date | None:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(part.strip(), fmt).date()
            except ValueError:
                continue
        return None

    start = _try(parts[0]) if parts else None
    end = _try(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Parse promotions from an Amex TH category hub (e.g., dining)."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    cards = soup.select(SELECTORS["promotion_card"])
    if not cards:
        # Fallback if Amex renames the AEM block.
        cards = soup.find_all("div", class_=re.compile(r"offer", re.I))

    logger.info("amex_cards_found", count=len(cards))

    for card in cards:
        promo = _parse_card(card)
        if promo:
            promotions.append(promo)

    return promotions


def _parse_card(card: Tag) -> Promotion | None:
    try:
        # Title lives inside .offer-header > p (not the wrapper div).
        title_el = card.select_one(SELECTORS["title"])
        title = normalize_thai_text(title_el.get_text(" ", strip=True)) if title_el else ""
        if not title or len(title) < 3:
            return None

        # Link: prefer the image-wrap link, fall back to the "อ่านเพิ่มเติม" CTA.
        link_el = card.select_one(SELECTORS["link"])
        href = ""
        if link_el:
            raw = link_el.get("href", "")
            if isinstance(raw, list):
                href = raw[0] if raw else ""
            else:
                href = raw
        if href:
            href = urljoin(PROMOTION_URL, href)

        # Amex detail-page slugs look like "dining.4k-cafe-cross-vibe-...html"
        # — use the last path segment minus `.html` as the source_id.
        last_segment = href.rstrip("/").split("/")[-1] if href else ""
        last_segment = re.sub(r"\?.*$", "", last_segment)
        last_segment = re.sub(r"\.html?$", "", last_segment)
        source_id = last_segment or title[:80]
        source_url = href or PROMOTION_URL

        # Image
        img_el = card.select_one(SELECTORS["image"])
        image_url: str | None = None
        if img_el:
            raw_img = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy-src")
            if isinstance(raw_img, list):
                image_url = raw_img[0] if raw_img else None
            else:
                image_url = raw_img
            if image_url and image_url.startswith("/"):
                image_url = BASE_URL + image_url

        # Description
        desc_el = card.select_one(SELECTORS["description"])
        description = normalize_thai_text(desc_el.get_text(" ", strip=True)) if desc_el else ""

        # Dates: Amex ships a dedicated .offer-dates slot in every tile.
        start_date, end_date = (None, None)
        date_el = card.select_one(SELECTORS["date"])
        if date_el:
            start_date, end_date = _parse_amex_date_range(date_el.get_text())

        full_text = title + " " + description
        discount_type, discount_value = extract_discount(full_text)
        minimum_spend = extract_minimum_spend(full_text)
        merchant_name = _extract_merchant_name(title, description)

        return Promotion(
            bank=BANK_NAME,
            source_id=source_id,
            source_url=source_url,
            title=title,
            description=description,
            image_url=image_url,
            merchant_name=merchant_name,
            category="dining",  # This parser is wired to the dining hub only.
            discount_type=discount_type,
            discount_value=discount_value,
            minimum_spend=minimum_spend,
            start_date=start_date,
            end_date=end_date,
            raw_data={"html_source": True, "title": title},
        )
    except Exception:
        logger.debug("amex_card_parse_error", exc_info=True)
        return None
