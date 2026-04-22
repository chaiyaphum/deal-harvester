from datetime import date
from pathlib import Path

from card_retrieval.adapters.amex.constants import HUB_CATEGORY_MAP, PROMOTION_HUBS
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


def test_parse_amex_travel_hub_fixture():
    """Travel hub fixture — same DOM, different merchants + category."""
    html = (FIXTURES / "amex_travel.html").read_text()
    promos = parse_promotions_from_html(
        html,
        category="travel",
        hub_url="https://www.americanexpress.com/th-th/benefits/promotions/travel.html",
    )
    assert len(promos) == 6

    for p in promos:
        assert p.bank == "amex"
        assert p.category == "travel"
        assert p.source_id.startswith("travel.")
        assert not p.source_id.endswith(".html")
        assert p.source_url.startswith(
            "https://www.americanexpress.com/th-th/benefits/promotions/travel."
        )

    # Parser should extract the 30%/40% discounts from the descriptions.
    discounts = {p.discount_value for p in promos if p.discount_value}
    assert any(d and "30%" in d for d in discounts)
    assert any(d and "40%" in d for d in discounts)


def test_parse_amex_lifestyle_hub_fixture():
    """Lifestyle hub maps to the `shopping` category."""
    html = (FIXTURES / "amex_lifestyle.html").read_text()
    promos = parse_promotions_from_html(
        html,
        category="shopping",
        hub_url="https://www.americanexpress.com/th-th/benefits/promotions/lifestyle.html",
    )
    assert len(promos) == 6

    for p in promos:
        assert p.bank == "amex"
        assert p.category == "shopping"
        assert p.source_id.startswith("lifestyle.")


def test_amex_hub_category_map_covers_all_hubs():
    """Every entry in PROMOTION_HUBS must have a category mapping."""
    for slug, _ in PROMOTION_HUBS:
        assert slug in HUB_CATEGORY_MAP, f"hub {slug!r} missing from HUB_CATEGORY_MAP"
    # explore-asia is regional travel, not its own category bucket.
    assert HUB_CATEGORY_MAP["explore-asia"] == "travel"
    # Lifestyle hub → "shopping" (dominated by retail/beauty merchants).
    assert HUB_CATEGORY_MAP["lifestyle"] == "shopping"


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


def test_amex_relative_hrefs_resolve_against_travel_hub():
    """When parser is given a travel hub_url, travel.foo.html should resolve there."""
    html = """
    <div class="offer parbase">
      <a class="link-underlined" href="travel.test-villa.html">
        <img class="card-detail-image" src="/content/villa.jpg">
      </a>
      <div class="offer-header"><p>Test Villa</p></div>
      <p class="offer-desc">ส่วนลด 30%</p>
      <div class="offer-dates">ระยะเวลา: 01/01/2026 - 31/12/2026</div>
    </div>
    """
    promos = parse_promotions_from_html(
        html,
        category="travel",
        hub_url="https://www.americanexpress.com/th-th/benefits/promotions/travel.html",
    )
    assert len(promos) == 1
    assert (
        promos[0].source_url
        == "https://www.americanexpress.com/th-th/benefits/promotions/travel.test-villa.html"
    )
    assert promos[0].category == "travel"


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
