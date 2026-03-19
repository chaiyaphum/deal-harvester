"""Tests for operations API endpoints: trigger, running, schedule."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from card_retrieval.api.app import api
from card_retrieval.core.models import ScrapeRun
from card_retrieval.storage.orm_models import Base
from card_retrieval.storage.repository import PromotionRepository

API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    session = sessionmaker(bind=db_engine)()
    yield session
    session.close()


@pytest.fixture
def repo(db_session):
    return PromotionRepository(session=db_session)


@pytest.fixture
def client(db_engine):
    """TestClient with repo override using shared in-memory SQLite."""
    import card_retrieval.adapters  # noqa: F401

    make_session = sessionmaker(bind=db_engine)

    def get_test_repo():
        r = PromotionRepository(session=make_session())
        r.close = lambda: None
        return r

    with patch("card_retrieval.api.routes._get_repo", side_effect=get_test_repo):
        yield TestClient(api)


# --- POST /api/v1/scrape/trigger ---


def test_trigger_scrape_single_bank(client):
    with patch("card_retrieval.api.routes._run_scrape_background", new_callable=AsyncMock):
        resp = client.post(
            "/api/v1/scrape/trigger",
            json={"bank": "ktc"},
            headers=HEADERS,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Scrape triggered"
    assert data["banks"] == ["ktc"]


def test_trigger_scrape_all_banks(client):
    with patch("card_retrieval.api.routes._run_scrape_background", new_callable=AsyncMock):
        resp = client.post(
            "/api/v1/scrape/trigger",
            json={},
            headers=HEADERS,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Scrape triggered"
    assert len(data["banks"]) >= 1


def test_trigger_scrape_unknown_bank(client):
    resp = client.post(
        "/api/v1/scrape/trigger",
        json={"bank": "nonexistent"},
        headers=HEADERS,
    )
    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


def test_trigger_scrape_conflict(client, repo):
    repo.save_scrape_run(ScrapeRun(bank="ktc", status="running"))

    resp = client.post(
        "/api/v1/scrape/trigger",
        json={"bank": "ktc"},
        headers=HEADERS,
    )
    assert resp.status_code == 409
    assert "ktc" in resp.json()["detail"]


def test_trigger_scrape_stale_run_ignored(client, repo):
    stale_run = ScrapeRun(bank="ktc", status="running")
    stale_run.started_at = datetime.utcnow() - timedelta(minutes=60)
    repo.save_scrape_run(stale_run)

    with patch("card_retrieval.api.routes._run_scrape_background", new_callable=AsyncMock):
        resp = client.post(
            "/api/v1/scrape/trigger",
            json={"bank": "ktc"},
            headers=HEADERS,
        )
    assert resp.status_code == 200


def test_trigger_scrape_no_auth(client):
    resp = client.post("/api/v1/scrape/trigger", json={"bank": "ktc"})
    assert resp.status_code == 401


# --- GET /api/v1/scrape/running ---


def test_running_empty(client):
    resp = client.get("/api/v1/scrape/running", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["banks"] == []


def test_running_with_active_scrape(client, repo):
    repo.save_scrape_run(ScrapeRun(bank="ktc", status="running"))
    repo.save_scrape_run(ScrapeRun(bank="cardx", status="success"))

    resp = client.get("/api/v1/scrape/running", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["banks"] == ["ktc"]


def test_running_excludes_stale(client, repo):
    stale_run = ScrapeRun(bank="ktc", status="running")
    stale_run.started_at = datetime.utcnow() - timedelta(minutes=60)
    repo.save_scrape_run(stale_run)

    resp = client.get("/api/v1/scrape/running", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["banks"] == []


# --- GET /api/v1/schedule ---


def test_schedule(client):
    resp = client.get("/api/v1/schedule", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    schedules = data["schedules"]
    assert len(schedules) >= 1
    banks = [s["bank"] for s in schedules]
    assert "ktc" in banks
    for s in schedules:
        assert "interval_hours" in s
        assert "rate_limit_seconds" in s
