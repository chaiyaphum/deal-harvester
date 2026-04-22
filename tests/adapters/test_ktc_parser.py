import json
from pathlib import Path

from card_retrieval.adapters.ktc.parser import (
    extract_next_data,
    parse_promotions_from_html,
    parse_promotions_from_next_data,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_extract_next_data_from_html():
    html = (FIXTURES / "ktc_promotion_page.html").read_text()
    data = extract_next_data(html)
    assert data is not None
    assert "props" in data
    assert "pageProps" in data["props"]


def test_parse_promotions_from_next_data():
    data = json.loads((FIXTURES / "ktc_next_data.json").read_text())
    promos = parse_promotions_from_next_data(data)

    assert len(promos) == 3

    # Check first promotion
    p1 = promos[0]
    assert p1.bank == "ktc"
    assert p1.source_id == "promo-001"
    assert "50%" in p1.title
    assert p1.discount_type == "percentage"
    assert p1.discount_value == "50%"
    assert p1.category == "dining"
    assert p1.start_date is not None
    assert p1.end_date is not None

    # Check cashback promotion
    p2 = promos[1]
    assert p2.discount_type == "cashback"
    assert "500" in (p2.discount_value or "")

    # Check points promotion
    p3 = promos[2]
    assert p3.discount_type == "points"
    assert p3.card_types == ["KTC VISA Signature"]


def test_parse_promotions_from_html_fallback():
    html = (FIXTURES / "ktc_promotion_page.html").read_text()
    promos = parse_promotions_from_html(html)
    assert len(promos) >= 2
    assert all(p.bank == "ktc" for p in promos)


def test_parse_next_data_full_page():
    """Test parsing __NEXT_DATA__ from a full HTML page."""
    html = (FIXTURES / "ktc_promotion_page.html").read_text()
    data = extract_next_data(html)
    assert data is not None
    promos = parse_promotions_from_next_data(data)
    assert len(promos) == 2  # The HTML fixture has 2 promos in __NEXT_DATA__


def _make_ktc_data(items: list[dict]) -> dict:
    return {"props": {"pageProps": {"promotions": items}}}


def test_ktc_merchant_from_explicit_json_field():
    """When JSON has merchantName, prefer it over title."""
    data = _make_ktc_data(
        [
            {
                "id": "p1",
                "slug": "p1",
                "title": "ลดราคา 50% ที่ร้านดัง",
                "merchantName": "Starbucks",
            }
        ]
    )
    promos = parse_promotions_from_next_data(data)
    assert len(promos) == 1
    assert promos[0].merchant_name == "Starbucks"


def test_ktc_merchant_falls_back_to_title():
    """When no merchant field, KTC titles usually ARE the merchant."""
    data = _make_ktc_data(
        [
            {
                "id": "p1",
                "slug": "p1",
                "title": "The North Face",
            }
        ]
    )
    promos = parse_promotions_from_next_data(data)
    assert len(promos) == 1
    assert promos[0].merchant_name == "The North Face"


def test_ktc_merchant_unwraps_dict_shape():
    """Some APIs return merchant as {name: ...}; handle that shape."""
    data = _make_ktc_data(
        [
            {
                "id": "p1",
                "slug": "p1",
                "title": "promo title",
                "merchant": {"name": "Uniqlo", "id": 42},
            }
        ]
    )
    promos = parse_promotions_from_next_data(data)
    assert promos[0].merchant_name == "Uniqlo"
