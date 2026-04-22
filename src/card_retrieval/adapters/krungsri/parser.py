from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup, Tag

from card_retrieval.adapters.krungsri.constants import (
    BANK_NAME,
    BASE_URL,
    PROMOTION_URL,
    SELECTORS,
)
from card_retrieval.core.models import Promotion
from card_retrieval.utils.text import extract_discount, extract_minimum_spend, normalize_thai_text

logger = structlog.get_logger()


# Krungsri promo copy usually identifies the merchant via Thai prepositions
# "ที่" / "ร่วมกับ". Merchant names come in three flavors:
#   (a) ALL-CAPS English:   "ที่ UNIQLO"
#   (b) Title-case English: "ที่ Centara Grand Buffet"
#   (c) Thai script:        "ที่ โรงแรมดุสิตธานี"
# Each alt captures one flavor. The lookahead allows end-of-string, Thai word
# boundaries, digits, or common Thai keyword transitions.
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
    r"บัตรเครดิต|บัตรเดบิต|กรุงศรี|Krungsri|BAY|KMA", re.IGNORECASE
)


THAI_MONTHS = {
    "ม.ค.": 1,
    "มกราคม": 1,
    "ก.พ.": 2,
    "กุมภาพันธ์": 2,
    "มี.ค.": 3,
    "มีนาคม": 3,
    "เม.ย.": 4,
    "เมษายน": 4,
    "พ.ค.": 5,
    "พฤษภาคม": 5,
    "มิ.ย.": 6,
    "มิถุนายน": 6,
    "ก.ค.": 7,
    "กรกฎาคม": 7,
    "ส.ค.": 8,
    "สิงหาคม": 8,
    "ก.ย.": 9,
    "กันยายน": 9,
    "ต.ค.": 10,
    "ตุลาคม": 10,
    "พ.ย.": 11,
    "พฤศจิกายน": 11,
    "ธ.ค.": 12,
    "ธันวาคม": 12,
}


def _extract_merchant_name(title: str, description: str) -> str | None:
    text = f"{title} {description}".strip()
    for pattern in _MERCHANT_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().rstrip(",.* ")
            if candidate and not _MERCHANT_BLOCKLIST.search(candidate):
                return candidate[:255]
    # ALL-CAPS English prefix often denotes a brand-led promo.
    caps_match = re.match(
        r"^([A-Z][A-Z0-9\s&.\-']{2,60}?)"
        r"(?=\s+[฀-๿]|\s+ผ่อน|\s+รับ|\s+0%|\s*$)",
        title,
    )
    if caps_match:
        candidate = caps_match.group(1).strip()
        if not _MERCHANT_BLOCKLIST.search(candidate):
            return candidate
    return None


def _parse_thai_date(part: str) -> date | None:
    part = part.strip()
    for month_name, month_num in THAI_MONTHS.items():
        if month_name in part:
            nums = re.findall(r"\d+", part)
            if len(nums) >= 2:
                day = int(nums[0])
                year = int(nums[-1])
                # Convert Buddhist era to CE if needed
                if year > 2500:
                    year -= 543
                elif year < 100:
                    # 2-digit BE abbreviation (e.g., "69" -> 2569 BE -> 2026 CE)
                    year += 2500 - 543
                try:
                    return date(year, month_num, day)
                except ValueError:
                    pass
            break
    return None


def _parse_iso_or_slash(part: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(part.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse Thai or ISO date-range strings like '1 ม.ค. 69 - 30 มิ.ย. 69'.

    The separator must be whitespace-padded so that intra-date hyphens
    (e.g., ``2026-04-01``) are not treated as range separators.
    """
    parts = re.split(r"\s+[-–~]\s+|\s+ถึง\s+", text, maxsplit=1)
    start = None
    end = None
    if parts:
        start = _parse_thai_date(parts[0]) or _parse_iso_or_slash(parts[0])
    if len(parts) > 1:
        end = _parse_thai_date(parts[1]) or _parse_iso_or_slash(parts[1])
    return start, end


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Parse promotions from the Krungsri promotion listing page."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    cards = soup.select(SELECTORS["promotion_card"])
    if not cards:
        # Broad fallback: any element whose class hints at a promotion card.
        cards = soup.find_all(
            ["a", "article", "div"], class_=re.compile(r"promo|card", re.I)
        )

    logger.info("krungsri_cards_found", count=len(cards))

    for card in cards:
        promo = _parse_card(card)
        if promo:
            promotions.append(promo)

    return promotions


def _parse_card(card: Tag) -> Promotion | None:
    try:
        # Title
        title_el = card.select_one(SELECTORS["title"])
        title = normalize_thai_text(title_el.get_text()) if title_el else ""
        if not title or len(title) < 3:
            return None

        # Link: either the card itself is an <a>, or contains one.
        href = ""
        if card.name == "a":
            href_attr = card.get(SELECTORS["link_attr"], "")
            href = href_attr if isinstance(href_attr, str) else ""
        if not href:
            a_tag = card.find("a", href=True)
            if a_tag:
                href_attr = a_tag.get("href", "")
                href = href_attr if isinstance(href_attr, str) else ""
        if href:
            href = urljoin(PROMOTION_URL, href)

        source_id = href.rstrip("/").split("/")[-1] if href else title[:80]
        source_url = href or PROMOTION_URL

        # Image (src or data-src for lazy-loaded)
        img_el = card.select_one(SELECTORS["image"])
        image_url: str | None = None
        if img_el:
            raw_img = (
                img_el.get("src")
                or img_el.get("data-src")
                or img_el.get("data-lazy-src")
            )
            if isinstance(raw_img, list):
                image_url = raw_img[0] if raw_img else None
            else:
                image_url = raw_img
            if image_url and image_url.startswith("/"):
                image_url = BASE_URL + image_url

        # Description
        desc_el = card.select_one(SELECTORS["description"])
        description = normalize_thai_text(desc_el.get_text()) if desc_el else ""

        # Category
        cat_el = card.select_one(SELECTORS["category"])
        category = normalize_thai_text(cat_el.get_text()) if cat_el else None

        # Date range
        date_el = card.select_one(SELECTORS["date"])
        start_date, end_date = (None, None)
        if date_el:
            start_date, end_date = _parse_date_range(date_el.get_text())

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
            category=category,
            discount_type=discount_type,
            discount_value=discount_value,
            minimum_spend=minimum_spend,
            start_date=start_date,
            end_date=end_date,
            raw_data={"html_source": True, "title": title},
        )
    except Exception:
        logger.debug("krungsri_card_parse_error", exc_info=True)
        return None
