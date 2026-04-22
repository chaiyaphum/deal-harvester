from datetime import date
from pathlib import Path

from card_retrieval.adapters.uob.parser import (
    _extract_merchant_name,
    _parse_date_range,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_uob_promotions_from_live_fixture():
    """Smoke test against a live-captured trimmed fixture (9 cards, 2026-04-22)."""
    html = (FIXTURES / "uob_promotions.html").read_text()
    promos = parse_promotions_from_html(html)

    # All 9 cards should parse.
    assert len(promos) == 9

    # Bank and absolute-URL handling.
    for p in promos:
        assert p.bank == "uob"
        assert p.source_url.startswith("https://")
        # relative image paths must get resolved to absolute.
        if p.image_url:
            assert p.image_url.startswith("https://www.uob.co.th/")

    # Source IDs must strip query strings so utm_* churn doesn't break dedupe.
    treasure = next(p for p in promos if "winner-announcement" in p.source_id)
    assert treasure.source_id == "winner-announcement.page"
    assert "?" not in treasure.source_id

    # The "Lady Gaga" card proves that the /revamp/ redirect URL flows through.
    lady_gaga = next(p for p in promos if "Lady Gaga" in p.title)
    assert lady_gaga.source_url.startswith("https://www.uob.co.th/revamp/")


def test_uob_strips_utm_query_from_source_id():
    """Two scrapes with different utm_source values must produce identical IDs."""
    html_template = """
    <div class="category-item">
      <div class="card">
        <img src="/img/a.jpg">
        <h4 class="card-title">Promo Title</h4>
        <p class="paragraph">รายละเอียดโปรโมชัน</p>
        <a class="dtm-button"
           href="/personal/promotions/creditcard/foo.page?utm_source={src}">CTA</a>
      </div>
    </div>
    """
    a = parse_promotions_from_html(html_template.format(src="a"))
    b = parse_promotions_from_html(html_template.format(src="b"))
    assert len(a) == len(b) == 1
    assert a[0].source_id == b[0].source_id == "foo.page"


def test_uob_relative_urls_resolved_against_hub():
    """Relative hrefs like '/personal/...' must resolve to absolute URLs."""
    html = """
    <div class="category-item">
      <div class="card">
        <img src="/assets/foo.jpg">
        <h4 class="card-title">ตัวอย่างโปรโมชัน</h4>
        <p class="paragraph">รายละเอียด</p>
        <a class="dtm-button" href="/personal/promotions/creditcard/sample.page">CTA</a>
      </div>
    </div>
    """
    promos = parse_promotions_from_html(html)
    assert len(promos) == 1
    assert (
        promos[0].source_url
        == "https://www.uob.co.th/personal/promotions/creditcard/sample.page"
    )
    assert promos[0].image_url == "https://www.uob.co.th/assets/foo.jpg"


def test_uob_parse_empty_html():
    assert parse_promotions_from_html("<html><body></body></html>") == []


def test_uob_merchant_extraction_thai_preposition_at():
    """The shared Thai merchant heuristic works for UOB titles too."""
    assert (
        _extract_merchant_name(
            "รับเครดิตเงินคืน 5% ที่ Starbucks ทุกสาขา",
            "",
        )
        == "Starbucks"
    )


def test_uob_merchant_blocklist_thai_month_names():
    """UOB descriptions include 'ที่ 18 มีนาคม' date phrasing; must not be treated as merchant."""
    assert (
        _extract_merchant_name(
            "Lady Gaga Presale",
            "จำหน่ายบัตร Presale: วันอังคารที่ 18 มีนาคม 2568 เวลา 10.00 น.",
        )
        is None
    )


def test_uob_merchant_blocklist_blocks_uob_brand():
    """Titles that only mention UOB's own brand should not yield a merchant."""
    assert (
        _extract_merchant_name(
            "รับส่วนลด 100 บาท ที่ UOB Cash Plus",
            "",
        )
        is None
    )


def test_uob_parse_date_range_western_slash_format():
    """UOB detail pages sometimes ship '01/04/2026 - 30/09/2026' date strings."""
    start, end = _parse_date_range("01/04/2026 - 30/09/2026")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 9, 30)


def test_uob_parse_date_range_buddhist_era():
    start, end = _parse_date_range("1 ม.ค. 69 - 30 มิ.ย. 69")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 6, 30)
