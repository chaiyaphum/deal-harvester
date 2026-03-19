from card_retrieval.core.models import Promotion, ScrapeRun


def test_upsert_new_promotions(repo):
    promos = [
        Promotion(
            bank="ktc",
            source_id="p1",
            source_url="https://ktc.co.th/p1",
            title="Promo 1",
        ),
        Promotion(
            bank="ktc",
            source_id="p2",
            source_url="https://ktc.co.th/p2",
            title="Promo 2",
        ),
    ]
    new, updated = repo.upsert_promotions(promos)
    assert new == 2
    assert updated == 0


def test_upsert_deduplication(repo):
    promo = Promotion(
        bank="ktc",
        source_id="p1",
        source_url="https://ktc.co.th/p1",
        title="Promo 1",
    )
    repo.upsert_promotions([promo])
    # Insert same again
    new, updated = repo.upsert_promotions([promo])
    assert new == 0
    assert updated == 0  # Same checksum, no update


def test_upsert_update_on_change(repo):
    promo = Promotion(
        bank="ktc",
        source_id="p1",
        source_url="https://ktc.co.th/p1",
        title="Original Title",
    )
    repo.upsert_promotions([promo])

    updated_promo = Promotion(
        bank="ktc",
        source_id="p1",
        source_url="https://ktc.co.th/p1",
        title="Updated Title",
    )
    new, updated = repo.upsert_promotions([updated_promo])
    assert new == 0
    assert updated == 1


def test_get_promotions(repo):
    promos = [
        Promotion(bank="ktc", source_id="k1", source_url="https://a.com", title="KTC 1"),
        Promotion(bank="cardx", source_id="c1", source_url="https://b.com", title="CardX 1"),
    ]
    repo.upsert_promotions(promos)

    all_promos = repo.get_promotions()
    assert len(all_promos) == 2

    ktc_promos = repo.get_promotions(bank="ktc")
    assert len(ktc_promos) == 1
    assert ktc_promos[0].bank == "ktc"


def test_save_scrape_run(repo):
    run = ScrapeRun(
        bank="ktc",
        status="success",
        promotions_found=10,
        promotions_new=5,
        promotions_updated=2,
    )
    repo.save_scrape_run(run)

    runs = repo.get_scrape_runs(bank="ktc")
    assert len(runs) == 1
    assert runs[0].bank == "ktc"
    assert runs[0].promotions_found == 10


def test_update_scrape_run(repo):
    from datetime import datetime

    run = ScrapeRun(bank="ktc", status="running")
    repo.save_scrape_run(run)

    # Verify it's saved as running
    runs = repo.get_scrape_runs(bank="ktc")
    assert runs[0].status == "running"
    assert runs[0].finished_at is None

    # Update to success
    run.status = "success"
    run.finished_at = datetime.utcnow()
    run.promotions_found = 50
    run.promotions_new = 10
    run.promotions_updated = 3
    repo.update_scrape_run(run)

    runs = repo.get_scrape_runs(bank="ktc")
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].finished_at is not None
    assert runs[0].promotions_found == 50
    assert runs[0].promotions_new == 10
    assert runs[0].promotions_updated == 3
