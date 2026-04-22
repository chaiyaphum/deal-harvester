from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from card_retrieval.adapters.bbl.parser import (
    _extract_image_url,
    _extract_merchant_name,
    _parse_date_range,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_bbl_promotions_mixed_fixture():
    """First tile is a live capture (2026-04-22); the other two are synthetic.

    See fixture header comment for the rationale — BBL's live EN hub only
    shipped one tile the day this adapter was written.
    """
    html = (FIXTURES / "bbl_promotions.html").read_text()
    promos = parse_promotions_from_html(html)

    assert len(promos) == 3

    # Bank + absolute-URL invariants.
    for p in promos:
        assert p.bank == "bbl"
        assert p.source_url.startswith("https://www.bangkokbank.com/")
        # BBL renders thumbnails as CSS background-image; parser must extract them.
        assert p.image_url is not None
        assert p.image_url.startswith("https://www.bangkokbank.com/-/media/")

    # Live card (Newsletter).
    p1 = promos[0]
    assert "Bangkok Bank" in p1.title
    assert p1.category == "Newsletter"
    assert p1.start_date == date(2026, 3, 1)
    assert p1.end_date == date(2026, 4, 30)

    # Synthetic Thai card with in-title "ที่ Centara Grand Buffet" merchant.
    p2 = promos[1]
    assert p2.merchant_name == "Centara Grand Buffet"
    assert p2.discount_type == "percentage"
    assert p2.discount_value == "20%"

    # Synthetic Thai card — minimum spend extracted, UNIQLO merchant.
    p3 = promos[2]
    assert p3.minimum_spend == 5000.0
    assert p3.merchant_name == "UNIQLO"
    assert p3.discount_type == "cashback"


def test_bbl_background_image_extraction():
    """BBL uses CSS `background-image: url(...)` on a div, not a plain <img>."""
    html = """
    <div class="thumb-default">
      <div class="thumb" style="background-image: url(/-/media/feature/foo.jpg)"></div>
      <div class="caption">
        <div class="desc">Test title</div>
      </div>
      <a class="btn-primary" href="/en/Promotions/X">x</a>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    card = soup.select_one(".thumb-default")
    url = _extract_image_url(card)
    assert url == "https://www.bangkokbank.com/-/media/feature/foo.jpg"


def test_bbl_parse_empty_html():
    assert parse_promotions_from_html("<html><body></body></html>") == []


def test_bbl_parse_date_range_en_until():
    """EN hub uses 'N MMM YYYY until N MMM YYYY'."""
    start, end = _parse_date_range("1 Mar 2026 until 30 Apr 2026")
    assert start == date(2026, 3, 1)
    assert end == date(2026, 4, 30)


def test_bbl_parse_date_range_thai_be_future_ready():
    """TH locale (once BBL restores it) ships '1 มี.ค. 2569 ถึง 30 เม.ย. 2569'."""
    start, end = _parse_date_range("1 มี.ค. 2569 ถึง 30 เม.ย. 2569")
    assert start == date(2026, 3, 1)
    assert end == date(2026, 4, 30)


def test_bbl_merchant_extraction_thai_at():
    assert _extract_merchant_name("เครดิตเงินคืน 10% ที่ Starbucks ทุกสาขา", "") == "Starbucks"


def test_bbl_merchant_extraction_english_at():
    """EN descriptions use 'at X' — pattern must match for English hub copy."""
    assert (
        _extract_merchant_name(
            "10% cashback at Starbucks",
            "",
        )
        == "Starbucks"
    )


def test_bbl_merchant_blocklist_blocks_bbl_and_months():
    """BBL's own brand names and English month names must be blocked."""
    assert _extract_merchant_name("Save 5% with Bangkok Bank", "") is None
    # "at May" from a descriptive sentence shouldn't surface as merchant
    assert _extract_merchant_name("Discount at May 2026", "") is None


def test_bbl_relative_href_resolves_to_absolute():
    html = """
    <div class="thumb-default">
      <div class="thumb" style="background-image: url(/img.jpg)"></div>
      <div class="caption"><div class="desc">Sample</div></div>
      <a class="btn-primary" href="/en/Personal/Cards/Credit-Cards/Promotions/Foo_260401">CTA</a>
    </div>
    """
    promos = parse_promotions_from_html(html)
    assert len(promos) == 1
    assert promos[0].source_url == (
        "https://www.bangkokbank.com/en/Personal/Cards/Credit-Cards/Promotions/Foo_260401"
    )
    assert promos[0].source_id == "Foo_260401"
