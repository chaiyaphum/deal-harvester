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


def test_checksum_changes_when_merchant_name_added():
    """Backfilling merchant_name on a previously-unparsed promo must invalidate checksum."""
    base = dict(
        bank="kasikorn",
        source_id="s1",
        source_url="https://example.com/1",
        title="Same title",
    )
    p_old = Promotion(**base)
    p_new = Promotion(**base, merchant_name="Starbucks")
    assert p_old.checksum != p_new.checksum


def test_checksum_changes_when_source_url_fixed():
    """Kasikorn URL-bug fix replaces broken '../pages/foo' URLs; checksum must detect."""
    base = dict(bank="kasikorn", source_id="s1", title="t")
    p_broken = Promotion(**base, source_url="https://www.kasikornbank.com../pages/foo.aspx")
    p_fixed = Promotion(
        **base, source_url="https://www.kasikornbank.com/th/promotion/creditcard/pages/foo.aspx"
    )
    assert p_broken.checksum != p_fixed.checksum


def test_checksum_changes_when_card_types_added():
    base = dict(bank="ktc", source_id="s1", source_url="https://example.com", title="t")
    p_empty = Promotion(**base)
    p_with_cards = Promotion(**base, card_types=["KTC VISA"])
    assert p_empty.checksum != p_with_cards.checksum


def test_checksum_stable_across_card_types_order():
    """card_types list order must not affect checksum (sorted before hashing)."""
    base = dict(bank="ktc", source_id="s1", source_url="https://example.com", title="t")
    p1 = Promotion(**base, card_types=["A", "B", "C"])
    p2 = Promotion(**base, card_types=["C", "A", "B"])
    assert p1.checksum == p2.checksum
