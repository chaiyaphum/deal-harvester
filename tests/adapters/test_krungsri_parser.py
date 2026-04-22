from datetime import date
from pathlib import Path

from card_retrieval.adapters.krungsri.parser import (
    _extract_merchant_name,
    _parse_date_range,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_krungsri_promotions():
    html = (FIXTURES / "krungsri_promotions.html").read_text()
    promos = parse_promotions_from_html(html)

    # Four cards in the fixture, all distinct source_ids.
    assert len(promos) == 4

    p1 = promos[0]
    assert p1.bank == "krungsri"
    assert "Centara" in p1.title
    assert p1.discount_type == "percentage"
    assert p1.discount_value == "50%"
    assert p1.category == "ร้านอาหาร"
    assert p1.source_url.startswith("https://www.krungsri.com/")
    assert p1.source_url.endswith("/dining-centara-buffet-50")
    assert p1.image_url is not None
    assert p1.image_url.startswith("https://www.krungsri.com/")

    # Buddhist-era 2-digit abbreviation: 69 BE = 2026 CE.
    assert p1.start_date == date(2026, 1, 1)
    assert p1.end_date == date(2026, 6, 30)

    p2 = promos[1]
    assert "UNIQLO" in p2.title
    assert p2.discount_type == "cashback"
    assert p2.discount_value and "500" in p2.discount_value
    assert p2.minimum_spend == 5000.0
    assert p2.merchant_name == "UNIQLO"

    p3 = promos[2]
    assert p3.discount_type == "points"
    # lazy-loaded image (data-src) should still resolve
    assert p3.image_url is not None
    # Full 4-digit BE year: 2569 BE = 2026 CE
    assert p3.start_date == date(2026, 3, 1)
    assert p3.end_date == date(2027, 2, 28)

    p4 = promos[3]
    # <article> wrapper with nested <a> — link must still be captured.
    assert p4.source_url.endswith("/auto-ptt-fuel-discount")


def test_parse_empty_html():
    assert parse_promotions_from_html("<html><body></body></html>") == []


def test_merchant_extraction_thai_preposition_at():
    assert (
        _extract_merchant_name(
            "ลดสูงสุด 50% ที่ Centara Grand Buffet 1 ม.ค. 69 - 30 มิ.ย. 69",
            "",
        )
        == "Centara Grand Buffet"
    )


def test_merchant_extraction_blocklist_blocks_bank_names():
    # Krungsri's own brand should not be treated as a merchant.
    assert (
        _extract_merchant_name(
            "รับส่วนลด 100 บาท เมื่อใช้จ่ายผ่านบัตรเครดิตกรุงศรี",
            "",
        )
        is None
    )


def test_merchant_extraction_all_caps_prefix():
    assert (
        _extract_merchant_name(
            "UNIQLO รับเครดิตเงินคืน 500 บาท",
            "",
        )
        == "UNIQLO"
    )


def test_parse_date_range_buddhist_two_digit():
    start, end = _parse_date_range("1 ม.ค. 69 - 30 มิ.ย. 69")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 6, 30)


def test_parse_date_range_buddhist_four_digit():
    start, end = _parse_date_range("1 มี.ค. 2569 - 28 ก.พ. 2570")
    assert start == date(2026, 3, 1)
    assert end == date(2027, 2, 28)


def test_parse_date_range_iso_fallback():
    start, end = _parse_date_range("2026-04-01 - 2026-04-30")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 4, 30)
