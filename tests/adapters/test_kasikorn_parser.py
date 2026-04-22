from pathlib import Path

from card_retrieval.adapters.kasikorn.parser import (
    _extract_merchant_name,
    parse_promotions_from_html,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_kbank_promotions():
    html = (FIXTURES / "kasikorn_promotions.html").read_text()
    promos = parse_promotions_from_html(html)

    assert len(promos) == 3

    p1 = promos[0]
    assert p1.bank == "kasikorn"
    assert "บุฟเฟ่ต์" in p1.title
    assert p1.discount_type == "percentage"
    assert p1.discount_value == "30%"
    assert p1.image_url is not None
    assert p1.source_url.startswith("https://www.kasikornbank.com")

    # Check date parsing for Thai dates
    assert p1.start_date is not None
    assert p1.start_date.year == 2024  # 67 BE = 2024 CE
    assert p1.start_date.month == 1

    p2 = promos[1]
    assert p2.discount_type == "points"
    assert p2.minimum_spend == 1000.0

    p3 = promos[2]
    assert "ประกันการเดินทาง" in p3.title
    assert p3.minimum_spend == 15000.0


def test_parse_empty_html():
    promos = parse_promotions_from_html("<html><body></body></html>")
    assert promos == []


def test_url_concat_resolves_parent_relative_paths():
    """Reproduce the '../pages/foo.aspx' → 'kasikornbank.com../pages/foo.aspx' bug.

    Fix uses urljoin so the '..' is resolved against the listing page URL.
    """
    html = """
    <div class="box-thumb">
      <a href="../pages/dining_sushiro.aspx" class="img-thumb">
        <img src="/th/promotion/creditcard/Documents/Image/sushiro.jpg" alt="">
      </a>
      <div class="thumb-title">รับส่วนลด 150 บาท ที่ Sushiro</div>
    </div>
    """
    promos = parse_promotions_from_html(html)
    assert len(promos) == 1
    url = promos[0].source_url
    assert ".." not in url, f"Bad URL (still contains '..'): {url}"
    assert url.startswith("https://www.kasikornbank.com/")
    # the "../" from ".../Pages/index.aspx" goes up to ".../creditcard/", then "pages/..." appends
    assert url.endswith("/pages/dining_sushiro.aspx")


def test_url_concat_absolute_path_unchanged():
    """Absolute '/th/...' hrefs still resolve to the full URL (existing fixture relies on this)."""
    html = """
    <div class="box-thumb">
      <a href="/th/promotion/creditcard/pages/foo.aspx" class="img-thumb">
        <img src="" alt="">
      </a>
      <div class="thumb-title">Sample title here</div>
    </div>
    """
    promos = parse_promotions_from_html(html)
    assert len(promos) == 1
    assert (
        promos[0].source_url
        == "https://www.kasikornbank.com/th/promotion/creditcard/pages/foo.aspx"
    )


def test_merchant_extraction_thai_preposition_at():
    """Titles with 'ที่ X' should yield X as merchant."""
    assert (
        _extract_merchant_name(
            "แบ่งจ่าย 0% นาน 3 เดือน ที่ AMERICAN SCHOOL OF BANGKOK SUKHUMVIT 1 ม.ค. 69 - 28 ก.พ. 70",
            "",
        )
        == "AMERICAN SCHOOL OF BANGKOK SUKHUMVIT"
    )


def test_merchant_extraction_blocklist_blocks_card_names():
    """Titles that use 'กสิกรไทย' / 'บัตรเครดิต' are the bank/card, not merchants."""
    assert (
        _extract_merchant_name(
            "รับส่วนลด 150 บาท กับ บัตรเครดิตกสิกรไทย",
            "",
        )
        is None
    )


def test_merchant_extraction_brand_led_all_caps_prefix():
    """Kasikorn sometimes leads with the brand in ALL CAPS English."""
    assert (
        _extract_merchant_name(
            "ASB GREEN VALLEY ผ่อน 0% นานสูงสุด 3 เดือน กับบัตรเครดิตกสิกรไทย",
            "",
        )
        == "ASB GREEN VALLEY"
    )


def test_merchant_extraction_returns_none_when_no_hint():
    """Titles without a merchant hint return None rather than guessing."""
    assert (
        _extract_merchant_name(
            "รับเครดิตเงินคืน 10% เมื่อใช้จ่ายครบ 10,000 บาท",
            "",
        )
        is None
    )
