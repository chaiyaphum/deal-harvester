import json
from pathlib import Path

from card_retrieval.adapters.cardx.parser import parse_intercepted_data

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_intercepted_api_response():
    data = json.loads((FIXTURES / "cardx_api_response.json").read_text())
    promos = parse_intercepted_data([data])

    assert len(promos) == 2

    p1 = promos[0]
    assert p1.bank == "cardx"
    assert p1.source_id == "cx-001"
    assert "Starbucks" in p1.title
    assert p1.merchant_name == "Starbucks"
    assert p1.discount_type == "percentage"
    assert p1.discount_value == "20%"
    assert p1.category == "dining"
    assert len(p1.card_types) == 2
    assert p1.start_date is not None
    assert p1.end_date is not None

    p2 = promos[1]
    assert p2.source_id == "cx-002"
    assert p2.discount_type == "cashback"
    assert "1000" in (p2.discount_value or "").replace(",", "")


def test_parse_empty_response():
    promos = parse_intercepted_data([])
    assert promos == []


def test_parse_malformed_response():
    promos = parse_intercepted_data([{"unknown_key": "value"}])
    assert promos == []
