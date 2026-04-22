from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup, Tag

from card_retrieval.adapters.bbl.constants import (
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


# BBL merchant heuristic reuses the Thai-preposition pattern. BBL tiles are
# usually Thai-language, but the EN hub occasionally ships English copy too.
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
        r")"
        + _MERCHANT_END
    ),
    re.compile(
        r"ร่วมกับ\s+("
        r"[A-Z][A-Z0-9\s&.\-']{2,60}"
        r"|[A-Z][a-zA-Z0-9\s&.\-']{2,60}?"
        r"|[฀-๿0-9\s&.\-']{3,60}?"
        r")"
        + _MERCHANT_END
    ),
    re.compile(
        r"at\s+("
        r"[A-Z][A-Za-z0-9\s&.\-']{2,60}?"
        r")"
        r"(?=\s+\d|\s+[\.,]|\s+during|\s+until|\s+for|\s*$)"
    ),
]

_MERCHANT_BLOCKLIST = re.compile(
    r"บัตรเครดิต|บัตรเดบิต|ธนาคารกรุงเทพ|Bangkok\s*Bank|BBL|"
    r"มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|"
    r"กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม|"
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December",
    re.IGNORECASE,
)


THAI_MONTHS = {
    "ม.ค.": 1, "มกราคม": 1,
    "ก.พ.": 2, "กุมภาพันธ์": 2,
    "มี.ค.": 3, "มีนาคม": 3,
    "เม.ย.": 4, "เมษายน": 4,
    "พ.ค.": 5, "พฤษภาคม": 5,
    "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7, "กรกฎาคม": 7,
    "ส.ค.": 8, "สิงหาคม": 8,
    "ก.ย.": 9, "กันยายน": 9,
    "ต.ค.": 10, "ตุลาคม": 10,
    "พ.ย.": 11, "พฤศจิกายน": 11,
    "ธ.ค.": 12, "ธันวาคม": 12,
}


def _extract_merchant_name(title: str, description: str) -> str | None:
    text = f"{title} {description}".strip()
    for pattern in _MERCHANT_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().rstrip(",.* ")
            if candidate and not _MERCHANT_BLOCKLIST.search(candidate):
                return candidate[:255]
    return None


def _parse_thai_date(part: str) -> date | None:
    part = part.strip()
    for month_name, month_num in THAI_MONTHS.items():
        if month_name in part:
            nums = re.findall(r"\d+", part)
            if len(nums) >= 2:
                day = int(nums[0])
                year = int(nums[-1])
                if year > 2500:
                    year -= 543
                elif year < 100:
                    year += 2500 - 543
                try:
                    return date(year, month_num, day)
                except ValueError:
                    pass
            break
    return None


def _parse_en_date(part: str) -> date | None:
    """Parse BBL-style EN dates like '1 Mar 2026' / '31 Apr 2026'."""
    part = part.strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(part, fmt).date()
        except ValueError:
            continue
    return None


def _parse_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse BBL date ranges.

    EN hub example: "1 Mar 2026 until 30 Apr 2026"
    TH pattern (future): "1 มี.ค. 2569 ถึง 30 เม.ย. 2569"
    """
    cleaned = text.strip()
    # BBL's listing tiles use "until" (EN) or "ถึง" (TH). Split on either.
    parts = re.split(r"\s+until\s+|\s+ถึง\s+|\s+[-–~]\s+", cleaned, maxsplit=1)
    start: date | None = None
    end: date | None = None
    if parts:
        start = _parse_en_date(parts[0]) or _parse_thai_date(parts[0])
    if len(parts) > 1:
        end = _parse_en_date(parts[1]) or _parse_thai_date(parts[1])
    return start, end


def _extract_image_url(card: Tag) -> str | None:
    """BBL renders thumbnails as CSS `background-image: url(...)` on a div.

    There's also a hidden `<img class="img-print">` with the same URL that
    prints cleanly; prefer the background-image, fall back to the img tag.
    """
    bg_el = card.select_one(SELECTORS["image_bg"])
    if bg_el:
        style = bg_el.get("style", "")
        if isinstance(style, list):
            style = " ".join(style)
        m = re.search(r"url\(([^)]+)\)", style or "")
        if m:
            url = m.group(1).strip(" '\"")
            return urljoin(BASE_URL, url) if url.startswith("/") else url

    fallback_el = card.select_one(SELECTORS["image_fallback"])
    if fallback_el:
        raw = fallback_el.get("src") or fallback_el.get("data-src")
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw and raw.startswith("/"):
            return BASE_URL + raw
        return raw
    return None


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Parse promotions from the BBL credit-card promotion hub."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    cards = soup.select(SELECTORS["promotion_card"])
    if not cards:
        cards = soup.find_all("div", class_=re.compile(r"thumb-default|promo", re.I))

    logger.info("bbl_cards_found", count=len(cards))

    for card in cards:
        promo = _parse_card(card)
        if promo:
            promotions.append(promo)

    return promotions


def _parse_card(card: Tag) -> Promotion | None:
    try:
        # Title / description share the same `.desc` slot in BBL's card
        # template; treat the first occurrence as the title.
        desc_el = card.select_one(SELECTORS["description"])
        title = normalize_thai_text(desc_el.get_text(" ", strip=True)) if desc_el else ""
        if not title or len(title) < 3:
            return None
        # BBL doesn't ship a separate description; duplicate the title so
        # downstream code always has something non-empty to show.
        description = title

        # Link (primary CTA).
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

        last_segment = href.rstrip("/").split("/")[-1] if href else ""
        last_segment = re.sub(r"\?.*$", "", last_segment)
        source_id = last_segment or title[:80]
        source_url = href or PROMOTION_URL

        image_url = _extract_image_url(card)

        cat_el = card.select_one(SELECTORS["category"])
        category = normalize_thai_text(cat_el.get_text(" ", strip=True)) if cat_el else None

        start_date, end_date = (None, None)
        date_el = card.select_one(SELECTORS["date"])
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
        logger.debug("bbl_card_parse_error", exc_info=True)
        return None
