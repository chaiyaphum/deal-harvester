from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup, Tag

from card_retrieval.adapters.uob.constants import (
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


# Reuse the Thai preposition merchant heuristic from Krungsri/Kasikorn.
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
]

# UOB itself, in all naming variants, must not be surfaced as the "merchant".
# Also block Thai month names — UOB descriptions often contain "ที่ <date>"
# phrasing ("เวลา ... ที่ 5 ตุลาคม 2567") which trips the "ที่" merchant
# pattern. Brand-led merchants never start with a month name.
_MERCHANT_BLOCKLIST = re.compile(
    r"บัตรเครดิต|บัตรเดบิต|ยูโอบี|UOB|Cash\s*Plus|"
    r"มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|"
    r"กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม",
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


def _parse_iso_or_slash(part: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(part.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse Thai or ISO date-range strings.

    UOB mixes formats: sometimes Thai BE like '1 ม.ค. 69 - 30 มิ.ย. 69',
    sometimes Western like '01/04/2026 - 30/09/2026'.
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
    """Parse promotions from the UOB Thailand credit-card promotion hub."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    cards = soup.select(SELECTORS["promotion_card"])
    if not cards:
        # Broad fallback if UOB renames the wrapper.
        cards = soup.find_all(
            "div", class_=re.compile(r"category-item|promo|card", re.I)
        )

    logger.info("uob_cards_found", count=len(cards))

    for card in cards:
        promo = _parse_card(card)
        if promo:
            promotions.append(promo)

    return promotions


def _parse_card(card: Tag) -> Promotion | None:
    try:
        # Title — UOB sometimes wraps the h4 inside another h4, so take the
        # deepest text.
        title_el = card.select_one(SELECTORS["title"])
        title = normalize_thai_text(title_el.get_text(" ", strip=True)) if title_el else ""
        if not title or len(title) < 3:
            return None

        # Link — prefer the dtm-button CTA but fall back to the first anchor.
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

        # UOB sometimes bounces internal CTAs through /personal/redirect/ or
        # through go.uob.com shorteners — preserve as-is; the source_id comes
        # from the path's last segment, minus query strings so utm_* noise
        # doesn't churn the checksum from one scrape to the next.
        last_segment = href.rstrip("/").split("/")[-1] if href else ""
        last_segment = re.sub(r"\?.*$", "", last_segment)
        source_id = last_segment or title[:80]
        source_url = href or PROMOTION_URL

        # Image
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
        description = normalize_thai_text(desc_el.get_text(" ", strip=True)) if desc_el else ""

        full_text = title + " " + description
        discount_type, discount_value = extract_discount(full_text)
        minimum_spend = extract_minimum_spend(full_text)
        merchant_name = _extract_merchant_name(title, description)

        # UOB doesn't have a structured date field in the listing card (dates
        # live on the promo detail page). Try to pull a range out of the
        # description as a best-effort.
        start_date, end_date = _parse_date_range(description)

        return Promotion(
            bank=BANK_NAME,
            source_id=source_id,
            source_url=source_url,
            title=title,
            description=description,
            image_url=image_url,
            merchant_name=merchant_name,
            category=None,
            discount_type=discount_type,
            discount_value=discount_value,
            minimum_spend=minimum_spend,
            start_date=start_date,
            end_date=end_date,
            raw_data={"html_source": True, "title": title},
        )
    except Exception:
        logger.debug("uob_card_parse_error", exc_info=True)
        return None
