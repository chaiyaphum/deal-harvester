from datetime import date
from pathlib import Path

from card_retrieval.adapters.krungsri.parser import (
    _extract_merchant_name,
    _parse_date_range,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_krungsri_promotions_from_live_fixture():
    """Live fixture captured 2026-04-22 from /th/promotions/cards/* categories."""
    html = (FIXTURES / "krungsri_promotions.html").read_text()
    promos = parse_promotions_from_html(html)

    # 11 tiles: 6 hot-promotion + 1 dining + 2 shopping-online + 2 travel.
    assert len(promos) == 11

    for p in promos:
        assert p.bank == "krungsri"
        assert p.source_url.startswith("https://www.krungsri.com/")
        assert p.title and len(p.title) >= 3

    by_id = {p.source_id: p for p in promos}

    hotels = by_id["discount-with-hotels"]
    assert "Hotels.com" in hotels.title
    assert hotels.discount_type == "percentage"
    assert hotels.discount_value == "7%"
    assert hotels.image_url is not None
    assert hotels.image_url.startswith("https://www.krungsri.com/")

    dining = by_id["dining-discount"]
    assert dining.discount_type == "percentage"
    assert dining.discount_value == "20%"

    avis = by_id["discount-with-avis"]
    assert avis.discount_type == "percentage"
    assert avis.discount_value == "20%"

    # FIFA promo carries no numeric discount — parser should return None cleanly.
    fifa = by_id["fifa-world-cup-2026"]
    assert fifa.discount_type is None
    assert fifa.discount_value is None

    # Listing pages don't ship inline dates or categories — parser must
    # gracefully surface None for both (the adapter stamps category based on
    # which hub the tile was fetched from).
    for p in promos:
        assert p.start_date is None
        assert p.end_date is None
        assert p.category is None


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
