from pathlib import Path

from card_retrieval.adapters.kasikorn.parser import parse_promotions_from_html

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
