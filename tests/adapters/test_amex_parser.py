from datetime import date
from pathlib import Path

from card_retrieval.adapters.amex.parser import (
    _extract_merchant_name,
    _parse_amex_date_range,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_amex_offers_from_live_fixture():
    """Smoke test against a live-captured trimmed fixture (8 dining offers)."""
    html = (FIXTURES / "amex_offers.html").read_text()
    promos = parse_promotions_from_html(html)

    assert len(promos) == 8

    # Every offer should be tagged as the amex bank + dining category.
    for p in promos:
        assert p.bank == "amex"
        assert p.category == "dining"
        assert p.source_url.startswith("https://www.americanexpress.com/")

    # First offer ships a structured date slot: "01/04/2026 - 30/09/2026".
    p1 = promos[0]
    assert p1.start_date == date(2026, 4, 1)
    assert p1.end_date == date(2026, 9, 30)
    assert "4K" in p1.title

    # source_id should strip the `.html` extension so it looks like a slug.
    assert p1.source_id.startswith("dining.4k-cafe")
    assert not p1.source_id.endswith(".html")

    # Image URLs are relative in the fixture; parser must resolve against BASE_URL.
    assert p1.image_url is not None
    assert p1.image_url.startswith("https://www.americanexpress.com/")


def test_amex_relative_hrefs_resolve_against_hub():
    """The in-page link is relative (`dining.foo.html`) and must resolve."""
    html = """
    <div class="offer parbase">
      <div class="card">
        <a class="link-underlined" href="dining.test-promo.html">
          <img class="card-detail-image" src="/content/img.jpg">
        </a>
        <div class="offer-header"><p>Test Merchant Ltd</p></div>
        <div class="offer-content">
          <p class="offer-desc">ส่วนลด 15% สำหรับอาหาร</p>
          <div class="offer-dates">ระยะเวลา: 01/05/2026 - 30/11/2026</div>
        </div>
      </div>
    </div>
    """
    promos = parse_promotions_from_html(html)
    assert len(promos) == 1
    p = promos[0]
    assert (
        p.source_url
        == "https://www.americanexpress.com/th-th/benefits/promotions/dining.test-promo.html"
    )
    assert p.source_id == "dining.test-promo"
    assert p.image_url == "https://www.americanexpress.com/content/img.jpg"


def test_amex_parse_empty_html():
    assert parse_promotions_from_html("<html><body></body></html>") == []


def test_amex_parse_date_range_with_thai_prefix():
    """Amex tiles use 'ระยะเวลา: DD/MM/YYYY - DD/MM/YYYY' — prefix must be stripped."""
    start, end = _parse_amex_date_range("ระยะเวลา: 01/04/2026 - 30/09/2026 ")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 9, 30)


def test_amex_parse_date_range_no_prefix():
    start, end = _parse_amex_date_range("01/06/2026 - 31/12/2026")
    assert start == date(2026, 6, 1)
    assert end == date(2026, 12, 31)


def test_amex_parse_date_range_invalid_returns_nones():
    start, end = _parse_amex_date_range("available soon")
    assert start is None
    assert end is None


def test_amex_merchant_extraction_thai_preposition():
    """Shared Thai preposition heuristic still works for Amex descriptions."""
    assert (
        _extract_merchant_name(
            "ส่วนลดพิเศษ",
            "รับส่วนลด 20% ที่ Blue Elephant Bangkok",
        )
        == "Blue Elephant Bangkok"
    )


def test_amex_merchant_fallback_uses_short_title():
    """When no 'ที่' hint exists, a short branded title IS the merchant."""
    assert (
        _extract_merchant_name("4K คาเฟ่ โรงแรมครอสไวบ์เชียงใหม่ดีเซม", "")
        == "4K คาเฟ่ โรงแรมครอสไวบ์เชียงใหม่ดีเซม"
    )


def test_amex_merchant_blocklist_blocks_amex_brand():
    """Brand-chrome titles must not surface as merchants."""
    assert _extract_merchant_name("American Express Platinum Benefit", "") is None
    assert _extract_merchant_name("สิทธิพิเศษบัตรเครดิตอเมริกัน เอ็กซ์เพรส", "") is None
