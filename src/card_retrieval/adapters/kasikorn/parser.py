from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup, Tag

from card_retrieval.adapters.kasikorn.constants import BANK_NAME, BASE_URL, PROMOTION_URL, SELECTORS
from card_retrieval.core.models import Promotion
from card_retrieval.utils.text import extract_discount, extract_minimum_spend, normalize_thai_text

logger = structlog.get_logger()

# Shared trailer lookahead — covers every common terminator we've seen on
# live KBank titles: digits (dates, amounts), Thai verbs that introduce the
# *promotion body* ("use", "receive", "enough"), Thai prepositions that start
# the amount clause ("in", "of"), date markers ("since", "on"), the branch
# marker ("branch"), and end-of-string.  The `|` alternates are greedy-free
# so the capture group stops at the first terminator.
_TRAILER = (
    r"(?=\s+\d|\s+ใช้จ่าย|\s+รับ|\s+ครบ|\s+เมื่อ|\s+ใน|\s+ของ|"
    r"\s+ตั้งแต่|\s+วันที่|\s+สาขา|\s+ผ่อน|\s+นาน|\s*[\-–]|\s*$)"
)

# Merchant-name candidate: either an ALL-CAPS English brand ("SUSHIRO",
# "ASB GREEN VALLEY") or a Thai-script name (brief, 3-60 chars).  Non-greedy
# so the trailer lookahead can terminate the capture early.
_MERCHANT_CAND = r"([A-Z][A-Z0-9\s&.\-']{2,60}|[฀-๿0-9\s&.\-']{3,60}?)"

_MERCHANT_PATTERNS = [
    # "ที่ <MERCHANT>" — "at <MERCHANT>"; the most common Thai promo phrasing.
    re.compile(rf"ที่\s+{_MERCHANT_CAND}{_TRAILER}"),
    # "ร่วมกับ <MERCHANT>" — "together with <MERCHANT>".
    re.compile(rf"ร่วมกับ\s+{_MERCHANT_CAND}{_TRAILER}"),
    # "จาก <MERCHANT>" — "from <MERCHANT>" (gift/voucher promos).
    re.compile(rf"จาก\s+{_MERCHANT_CAND}{_TRAILER}"),
    # "กับ <MERCHANT>" — bare "with <MERCHANT>" (tighter than ร่วมกับ so we
    # run it after).  Disallow "กับ บัตร…" via the blocklist downstream.
    re.compile(rf"(?<!ร่วม)กับ\s+{_MERCHANT_CAND}{_TRAILER}"),
    # "@ <MERCHANT>" — common brand-tag on shorter titles.
    re.compile(rf"@\s*{_MERCHANT_CAND}{_TRAILER}"),
]

_MERCHANT_BLOCKLIST = re.compile(
    r"บัตรเครดิต|บัตรเดบิต|K\+?\s*SHOP|KBank|กสิกรไทย|เครดิตเงินคืน|ร้านค้า",
    re.IGNORECASE,
)


def _extract_merchant_name(title: str, description: str) -> str | None:
    text = f"{title} {description}".strip()
    for pattern in _MERCHANT_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().rstrip(",.*-– ")
            if candidate and not _MERCHANT_BLOCKLIST.search(candidate):
                return candidate[:255]
    # ALL-CAPS English prefix often denotes a brand-led promo (e.g.
    # "ASB GREEN VALLEY ผ่อน 0%…").  Keep this check last so the preposition
    # patterns win for titles that have both.
    caps_match = re.match(
        r"^([A-Z][A-Z0-9\s&.\-']{2,60}?)"
        r"(?=\s+[฀-๿]|\s+ผ่อน|\s+รับ|\s+0%|\s+ผ่อ|\s*$)",
        title,
    )
    if caps_match:
        candidate = caps_match.group(1).strip()
        if not _MERCHANT_BLOCKLIST.search(candidate):
            return candidate
    return None


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


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Parse promotions from KBank rendered HTML."""
    soup = BeautifulSoup(html, "lxml")
    promotions: list[Promotion] = []

    cards = soup.select(SELECTORS["promotion_card"])
    if not cards:
        # Broad fallback: find any elements that look like promotion cards
        cards = soup.find_all("div", class_=re.compile(r"promo|card|item", re.I))

    logger.info("kbank_cards_found", count=len(cards))

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

        # Link — use urljoin so "../pages/..." and "/abs" and absolute URLs all resolve correctly
        link_el = card.select_one(SELECTORS["link"])
        href = ""
        if link_el:
            href = link_el.get("href", "")
            if isinstance(href, list):
                href = href[0] if href else ""
        if href:
            href = urljoin(PROMOTION_URL, href)

        source_id = href.rstrip("/").split("/")[-1] if href else title[:80]
        source_url = href or PROMOTION_URL

        # Image
        img_el = card.select_one(SELECTORS["image"])
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy-src")
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else None
            if image_url and image_url.startswith("/"):
                image_url = BASE_URL + image_url

        # Description
        desc_el = card.select_one(SELECTORS["description"])
        description = normalize_thai_text(desc_el.get_text()) if desc_el else ""

        # Date
        date_el = card.select_one(SELECTORS["date"])
        start_date, end_date = None, None
        if date_el:
            date_text = date_el.get_text()
            start_date, end_date = _parse_date_range(date_text)

        # Category
        cat_el = card.select_one(SELECTORS["category"])
        category = normalize_thai_text(cat_el.get_text()) if cat_el else None

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
        logger.debug("kbank_card_parse_error", exc_info=True)
        return None


def _parse_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse Thai date range strings like '1 ม.ค. 67 - 31 มี.ค. 67'."""

    def _parse_thai_date(part: str) -> date | None:
        part = part.strip()
        for month_name, month_num in THAI_MONTHS.items():
            if month_name in part:
                # Extract day and year
                nums = re.findall(r"\d+", part)
                if len(nums) >= 2:
                    day = int(nums[0])
                    year = int(nums[-1])
                    # Convert Buddhist era to CE
                    if year > 2500:
                        year -= 543
                    elif year < 100:
                        year += 2500 - 543  # e.g., 67 -> 2024
                    try:
                        return date(year, month_num, day)
                    except ValueError:
                        pass
                break
        return None

    # Also try standard date formats
    def _try_standard(part: str) -> date | None:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(part.strip(), fmt).date()
            except ValueError:
                continue
        return None

    parts = re.split(r"\s*[-–~ถึง]\s*", text, maxsplit=1)

    start = _parse_thai_date(parts[0]) or _try_standard(parts[0]) if parts else None
    end = None
    if len(parts) > 1:
        end = _parse_thai_date(parts[1]) or _try_standard(parts[1])

    return start, end
