from datetime import date

from card_retrieval.core.models import Promotion


def test_promotion_checksum_deterministic():
    p1 = Promotion(
        bank="ktc",
        source_id="test-1",
        source_url="https://example.com/1",
        title="Test Promo",
    )
    p2 = Promotion(
        bank="ktc",
        source_id="test-1",
        source_url="https://example.com/1",
        title="Test Promo",
    )
    assert p1.checksum == p2.checksum


def test_promotion_checksum_changes_on_content_change():
    p1 = Promotion(
        bank="ktc",
        source_id="test-1",
        source_url="https://example.com/1",
        title="Original Title",
    )
    p2 = Promotion(
        bank="ktc",
        source_id="test-1",
        source_url="https://example.com/1",
        title="Updated Title",
    )
    assert p1.checksum != p2.checksum


def test_promotion_defaults():
    p = Promotion(
        bank="test",
        source_id="1",
        source_url="https://example.com",
        title="Test",
    )
    assert p.card_types == []
    assert p.raw_data == {}
    assert p.id  # UUID generated
    assert p.scraped_at  # datetime generated


def test_promotion_with_dates():
    p = Promotion(
        bank="ktc",
        source_id="test-1",
        source_url="https://example.com",
        title="Test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert p.start_date == date(2024, 1, 1)
    assert p.end_date == date(2024, 12, 31)
