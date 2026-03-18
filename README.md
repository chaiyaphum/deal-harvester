# Card Data Retrieval

Automated credit card promotion scraper for Thai bank websites. Supports 3 banks (KTC, CardX, Kasikorn) with a plugin architecture that makes adding new banks easy. Includes a REST API for querying promotion data.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage (CLI)](#usage-cli)
- [Configuration](#configuration)
- [REST API](#rest-api)
- [CI/CD](#cicd)
- [Component Reference](#component-reference)
  - [Core Layer](#1-core-layer)
  - [Adapters](#2-adapters)
  - [Fetchers](#3-fetchers)
  - [Storage Layer](#4-storage-layer)
  - [Scheduling](#5-scheduling)
  - [Utilities](#6-utilities)
- [Data Schema](#data-schema)
- [Database](#database)
- [Adding a New Bank](#adding-a-new-bank)
- [Testing](#testing)
- [Deployment](#deployment)

---

## Overview

The system:

1. **Scrapes promotions** from 3 Thai bank websites, each using different techniques based on site complexity
2. **Parses data** into a unified schema across all banks
3. **Stores to database** with checksum-based deduplication (re-runs never create duplicates)
4. **Soft-deletes** promotions that disappear from the source site
5. **Runs on a schedule** via built-in scheduler
6. **Serves a REST API** for querying promotions, stats, and scrape history
7. **Logs audit trail** for every scrape run
8. **Alerts on repeated failures** (3+ consecutive fails per adapter)

| Bank | Website | Difficulty | Scraping Method |
|------|---------|-----------|-----------------|
| **KTC** | ktc.co.th/promotion | Easy-Medium | HTTP request + `__NEXT_DATA__` JSON parsing (Next.js SSR) |
| **CardX** | cardx.co.th/credit-card/promotion | Hard | Playwright browser + API response interception (Flutter SPA) |
| **Kasikorn** | kasikornbank.com | Very Hard | Stealth Playwright (anti-bot detection, headed mode required) |

---

## Architecture

```
                ┌─────────────┐     ┌──────────────┐
                │  CLI (typer) │     │  FastAPI      │
                │  / Scheduler │     │  REST API     │
                └──────┬──────┘     └──────┬───────┘
                       │                   │
                       v                   │
              ┌────────────────┐           │
              │   Pipeline     │           │
              │  (pipeline.py) │           │
              └────────┬───────┘           │
                       │                   │
          ┌────────────┼────────────┐      │
          v            v            v      │
   ┌────────────┐ ┌──────────┐ ┌───────────┐  │
   │ KTC        │ │ CardX    │ │ Kasikorn  │  │
   │ Adapter    │ │ Adapter  │ │ Adapter   │  │
   └─────┬──────┘ └────┬─────┘ └─────┬─────┘  │
         │              │              │       │
         v              v              v       │
   ┌──────────┐  ┌───────────┐  ┌────────────┐│
   │ HTTP     │  │ Browser   │  │ Stealth    ││
   │ Fetcher  │  │ Fetcher   │  │ Fetcher    ││
   │ (httpx)  │  │(Playwright│  │(Playwright ││
   │          │  │+intercept)│  │+anti-detect││
   └──────────┘  └───────────┘  └────────────┘│
                       │                       │
                       v                       v
              ┌────────────────────────────────────┐
              │           Repository               │
              │         (SQLAlchemy)                │
              └────────────────┬───────────────────┘
                               │
                               v
              ┌────────────────────────────────────┐
              │      PostgreSQL / SQLite            │
              └────────────────────────────────────┘
```

The **CLI/Scheduler** path runs the scraping pipeline: fetch → parse → store → soft-delete.
The **REST API** path reads directly from the repository to serve promotion data via HTTP.

### Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **Registry** | `core/registry.py` | Adapters self-register via `@register("bank_name")` decorator — no pipeline changes needed |
| **Strategy** | Each Adapter | Different scraping technique per bank, same interface |
| **Template Method** | `BaseAdapter` | Defines the contract all adapters must implement |
| **Repository** | `storage/repository.py` | Separates business logic from database access |
| **Pipeline** | `core/pipeline.py` | Orchestrates: fetch -> parse -> normalize -> store -> soft-delete |

---

## Project Structure

```
card-data-retrieval/
├── pyproject.toml                          # Project metadata + dependencies
├── alembic.ini                             # Alembic migration config
├── Dockerfile                              # Production Docker image
├── docker-compose.yml                      # Docker Compose for deployment
├── entrypoint.sh                           # Container entrypoint (migrate + schedule)
├── .dockerignore
│
├── .github/
│   └── workflows/
│       ├── ci.yml                          # CI: lint (ruff) + test (pytest)
│       └── deploy.yml                      # CD: auto-deploy to DigitalOcean on main
│
├── alembic/
│   ├── env.py                              # Alembic environment (uses settings.database_url)
│   ├── script.py.mako                      # Migration template
│   └── versions/                           # Auto-generated migration files
│
├── src/card_retrieval/
│   ├── __init__.py
│   ├── main.py                             # CLI entry point (typer)
│   ├── config.py                           # Settings from environment variables
│   │
│   ├── api/                                # REST API (FastAPI)
│   │   ├── app.py                          # FastAPI app, custom Swagger UI with pre-auth
│   │   ├── auth.py                         # API key authentication (X-API-Key header)
│   │   ├── routes.py                       # All API endpoints (/api/v1/*)
│   │   └── schemas.py                      # Pydantic response models
│   │
│   ├── core/                               # Core business logic
│   │   ├── base_adapter.py                 # Abstract base class for adapters
│   │   ├── registry.py                     # Adapter registry system
│   │   ├── models.py                       # Pydantic schemas (Promotion, ScrapeRun)
│   │   ├── pipeline.py                     # Orchestrator (run adapter -> store -> audit)
│   │   └── exceptions.py                   # Custom exceptions
│   │
│   ├── adapters/                           # Per-bank adapters
│   │   ├── __init__.py                     # Imports all adapters to trigger registration
│   │   ├── ktc/
│   │   │   ├── adapter.py                  # KtcAdapter class
│   │   │   ├── parser.py                   # HTML/JSON -> Promotion parsing
│   │   │   └── constants.py                # URLs, rate limits, 15 category slugs
│   │   ├── cardx/
│   │   │   ├── adapter.py                  # CardxAdapter class
│   │   │   ├── parser.py                   # Intercepted JSON -> Promotion parsing
│   │   │   └── constants.py                # URLs, API patterns
│   │   └── kasikorn/
│   │       ├── adapter.py                  # KasikornAdapter class
│   │       ├── parser.py                   # Rendered HTML -> Promotion + Thai date parsing
│   │       └── constants.py                # URLs, CSS selectors
│   │
│   ├── fetchers/                           # Web fetching layer
│   │   ├── http_fetcher.py                 # httpx (async HTTP/2) + retry
│   │   ├── browser_fetcher.py              # Playwright (JS rendering + API intercept)
│   │   └── stealth_fetcher.py              # Playwright + anti-bot (human-like behavior)
│   │
│   ├── storage/                            # Database layer
│   │   ├── database.py                     # SQLAlchemy engine + session
│   │   ├── orm_models.py                   # Table definitions (PromotionRow, ScrapeRunRow)
│   │   └── repository.py                   # CRUD + upsert + dedup + soft-delete
│   │
│   ├── scheduling/
│   │   └── scheduler.py                    # APScheduler async jobs
│   │
│   └── utils/
│       ├── text.py                         # Thai text normalization + discount extraction
│       └── rate_limiter.py                 # Per-domain rate limiting
│
├── tests/
│   ├── conftest.py                         # Pytest fixtures (in-memory DB)
│   ├── test_models.py                      # Promotion checksum tests
│   ├── test_registry.py                    # Adapter registration tests
│   ├── test_repository.py                  # Upsert + dedup tests
│   ├── test_text_utils.py                  # Thai text parsing tests
│   ├── adapters/
│   │   ├── test_ktc_parser.py              # KTC parser tests (against fixtures)
│   │   ├── test_cardx_parser.py            # CardX parser tests
│   │   └── test_kasikorn_parser.py         # Kasikorn parser tests
│   └── fixtures/
│       ├── ktc_next_data.json              # Sample KTC __NEXT_DATA__
│       ├── ktc_promotion_page.html         # Sample KTC HTML page
│       ├── cardx_api_response.json         # Sample CardX API response
│       └── kasikorn_promotions.html        # Sample Kasikorn HTML page
│
└── data/
    └── promotions.db                       # SQLite database (auto-created, local dev only)
```

---

## Installation

### Step 1: Install uv (package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### Step 2: Create virtual environment + install dependencies

```bash
cd card-data-retrieval
uv venv --python 3.11
uv pip install -e ".[dev]"
```

### Step 3: Install Playwright browsers (required for CardX + Kasikorn)

```bash
.venv/bin/playwright install chromium
```

### Step 4: Initialize the database

```bash
card-retrieval init-db
alembic upgrade head
```

---

## Usage (CLI)

All commands are available via:

```bash
card-retrieval <command>
```

### Commands

#### `run` — Run the scraper

```bash
# Scrape all banks
card-retrieval run

# Scrape a specific bank
card-retrieval run --bank ktc

# Dry run: fetch and parse but skip DB writes
card-retrieval run --bank ktc --dry-run
```

Output:
```
Starting scrape for all banks...
  ktc: success | found=160 new=160 updated=0
  cardx: success | found=14 new=14 updated=0
  kasikorn: success | found=49 new=49 updated=0
```

#### `list-adapters` — Show registered adapters

```bash
card-retrieval list-adapters
```

#### `show` — Display stored promotions

```bash
card-retrieval show
card-retrieval show --bank ktc --limit 50
```

#### `history` — Show scrape run audit log

```bash
card-retrieval history
card-retrieval history --bank ktc --limit 5
```

#### `schedule` — Start the periodic scheduler

```bash
card-retrieval schedule
```

```
Starting scheduler...
  KTC: every 6h
  CardX: every 12h
  Kasikorn: every 24h
```

Press `Ctrl+C` to stop.

#### `serve` — Start the REST API server

```bash
# Default: 0.0.0.0:8000
card-retrieval serve

# Custom host/port
card-retrieval serve --host 127.0.0.1 --port 3000
```

Swagger UI is available at `http://<host>:<port>/docs`. ReDoc at `/redoc`.

#### `init-db` — Create database tables

```bash
card-retrieval init-db
```

---

## Configuration

All settings are configured via **environment variables** with the `CARD_RETRIEVAL_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `CARD_RETRIEVAL_DATABASE_URL` | `sqlite:///data/promotions.db` | Database connection string |
| `CARD_RETRIEVAL_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `CARD_RETRIEVAL_LOG_JSON` | `false` | Enable JSON logging (recommended for production) |
| `CARD_RETRIEVAL_RATE_LIMIT_KTC` | `2.0` | Seconds between KTC requests |
| `CARD_RETRIEVAL_RATE_LIMIT_CARDX` | `5.0` | Seconds between CardX requests |
| `CARD_RETRIEVAL_RATE_LIMIT_KASIKORN` | `10.0` | Seconds between Kasikorn requests |
| `CARD_RETRIEVAL_SCHEDULE_KTC` | `6` | Hours between KTC scrape cycles |
| `CARD_RETRIEVAL_SCHEDULE_CARDX` | `12` | Hours between CardX scrape cycles |
| `CARD_RETRIEVAL_SCHEDULE_KASIKORN` | `24` | Hours between Kasikorn scrape cycles |
| `CARD_RETRIEVAL_BROWSER_HEADLESS` | `true` | Run browser in headless mode (set `false` for Kasikorn) |
| `CARD_RETRIEVAL_BROWSER_TIMEOUT` | `30000` | Browser timeout in milliseconds |
| `CARD_RETRIEVAL_API_KEYS` | `""` (empty) | Comma-separated API keys for REST API authentication |

Example:

```bash
# Use PostgreSQL instead of SQLite
export CARD_RETRIEVAL_DATABASE_URL="postgresql://user:pass@localhost:5432/card_promo"

# Enable debug logging
export CARD_RETRIEVAL_LOG_LEVEL="DEBUG"

# Show browser window (required for Kasikorn, useful for debugging)
export CARD_RETRIEVAL_BROWSER_HEADLESS="false"

# Set API keys (comma-separated for multiple keys)
export CARD_RETRIEVAL_API_KEYS="my-secret-key-1,my-secret-key-2"
```

Or create a `.env` file:

```env
CARD_RETRIEVAL_DATABASE_URL=sqlite:///data/promotions.db
CARD_RETRIEVAL_LOG_LEVEL=INFO
CARD_RETRIEVAL_BROWSER_HEADLESS=true
CARD_RETRIEVAL_API_KEYS=my-secret-key
```

---

## REST API

The REST API provides read-only access to scraped promotion data. It runs as a separate service alongside the scraper/scheduler.

### Base URL

```
http://<host>:8000/api/v1
```

- **Swagger UI:** `http://<host>:8000/docs` (pre-authorized with the first configured API key)
- **ReDoc:** `http://<host>:8000/redoc`

### Authentication

All endpoints except `/health` require an API key via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/promotions
```

If `CARD_RETRIEVAL_API_KEYS` is empty, any non-empty key is accepted (useful for development).

### Endpoints

#### `GET /api/v1/health` — Health check (public)

No authentication required.

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "adapters": ["ktc", "cardx", "kasikorn"]
}
```

#### `GET /api/v1/promotions` — List promotions

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bank` | string | — | Filter by bank (e.g. `ktc`, `cardx`, `kasikorn`) |
| `category` | string | — | Filter by category slug |
| `merchant_name` | string | — | Partial match on merchant name |
| `discount_type` | string | — | Filter by discount type (`percentage`, `cashback`, `discount`, `points`) |
| `card_type` | string | — | Filter promotions containing this card type |
| `search` | string | — | Full-text search on title and description |
| `is_active` | bool | `true` | Filter by active status |
| `start_date_from` | date | — | Promotions starting on or after this date |
| `start_date_to` | date | — | Promotions starting on or before this date |
| `end_date_from` | date | — | Promotions ending on or after this date |
| `end_date_to` | date | — | Promotions ending on or before this date |
| `min_spend_min` | float | — | Minimum spend >= value |
| `min_spend_max` | float | — | Minimum spend <= value |
| `sort_by` | string | `scraped_at` | Sort field |
| `sort_order` | string | `desc` | `asc` or `desc` |
| `page` | int | `1` | Page number (>= 1) |
| `page_size` | int | `20` | Items per page (1-100) |

```bash
# All active KTC promotions with cashback
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/promotions?bank=ktc&discount_type=cashback"

# Search promotions expiring after 2025-01-01
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/promotions?end_date_from=2025-01-01&search=starbucks"
```

```json
{
  "items": [
    {
      "id": "abc-123",
      "bank": "ktc",
      "source_id": "promo-456",
      "source_url": "https://www.ktc.co.th/promotion/...",
      "title": "Starbucks 15% Cashback",
      "description": "...",
      "image_url": "https://...",
      "card_types": ["KTC VISA PLATINUM"],
      "category": "dining-restaurants",
      "merchant_name": "Starbucks",
      "discount_type": "cashback",
      "discount_value": "15%",
      "minimum_spend": 300.0,
      "start_date": "2025-01-01",
      "end_date": "2025-06-30",
      "terms_and_conditions": "...",
      "is_active": true,
      "scraped_at": "2025-03-15T10:30:00",
      "created_at": "2025-03-15T10:30:00",
      "updated_at": "2025-03-15T10:30:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

#### `GET /api/v1/promotions/{id}` — Get a single promotion

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/promotions/abc-123
```

Returns a single `PromotionResponse` object, or `404` if not found.

#### `GET /api/v1/scrape-runs` — Scrape run history

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bank` | string | — | Filter by bank |
| `status` | string | — | Filter by status (`running`, `success`, `failed`) |
| `from_date` | datetime | — | Runs started after this time |
| `to_date` | datetime | — | Runs started before this time |
| `page` | int | `1` | Page number |
| `page_size` | int | `20` | Items per page (1-100) |

```bash
curl -H "X-API-Key: your-key" "http://localhost:8000/api/v1/scrape-runs?bank=ktc&status=success"
```

```json
{
  "items": [
    {
      "id": "run-789",
      "bank": "ktc",
      "started_at": "2025-03-15T10:00:00",
      "finished_at": "2025-03-15T10:00:32",
      "status": "success",
      "promotions_found": 160,
      "promotions_new": 3,
      "promotions_updated": 1,
      "error_message": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

#### `GET /api/v1/stats` — Promotion statistics per bank

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/stats
```

```json
[
  {"bank": "ktc", "total": 160, "active": 155},
  {"bank": "cardx", "total": 14, "active": 14},
  {"bank": "kasikorn", "total": 49, "active": 45}
]
```

#### `GET /api/v1/filters` — Available filter options

Returns the distinct values currently in the database, useful for building filter UIs.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/filters
```

```json
{
  "banks": ["cardx", "kasikorn", "ktc"],
  "categories": ["dining-restaurants", "shopping", "travel", "..."],
  "discount_types": ["cashback", "discount", "percentage", "points"],
  "card_types": ["KTC VISA PLATINUM", "..."],
  "merchant_names": ["Starbucks", "..."]
}
```

---

## CI/CD

The project uses GitHub Actions for continuous integration and deployment.

### CI Workflow (`.github/workflows/ci.yml`)

Runs on every push to `main` and on pull requests targeting `main`:

1. **Lint** — `ruff check` and `ruff format --check` on `src/` and `tests/`
2. **Test** — `pytest tests/ -v` (runs after lint passes)

### Deploy Workflow (`.github/workflows/deploy.yml`)

Triggered automatically when the CI workflow succeeds on `main`:

1. SSHs into the DigitalOcean droplet
2. Pulls the latest code (`git pull origin main`)
3. Rebuilds and restarts Docker containers (`docker compose up -d --build --force-recreate`)
4. Cleans up old Docker images

```
Push to main → CI (lint + test) → Deploy (SSH → git pull → docker compose up)
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DROPLET_HOST` | DigitalOcean droplet IP address |
| `DROPLET_SSH_KEY` | SSH private key for root access to the droplet |

---

## Component Reference

### 1. Core Layer

#### `core/models.py` — Pydantic Schemas

**Promotion** — A single promotion record:

```python
class Promotion(BaseModel):
    id: str                          # Auto-generated UUID
    bank: str                        # "ktc", "cardx", "kasikorn"
    source_id: str                   # Original ID from the bank website
    source_url: str                  # Direct URL to the promotion page
    title: str                       # Promotion title
    description: str                 # Details
    image_url: str | None            # Image URL
    card_types: list[str]            # Eligible card types
    category: str | None             # "dining", "shopping", "travel", ...
    merchant_name: str | None        # Merchant name
    discount_type: str | None        # "percentage", "cashback", "points", "discount"
    discount_value: str | None       # "50%", "500 baht", "5000 points"
    minimum_spend: float | None      # Minimum spend amount (THB)
    start_date: date | None          # Start date
    end_date: date | None            # End date
    terms_and_conditions: str | None # Terms
    raw_data: dict                   # Raw source data (for debugging)
    scraped_at: datetime             # Scrape timestamp
    checksum: str                    # SHA-256 (computed) for change detection
```

**checksum** is computed from: `bank + source_id + title + description + discount_type + discount_value + start_date + end_date`, hashed with SHA-256. Used to detect whether data has changed between scrapes.

**ScrapeRun** — Audit record for each scrape execution:

```python
class ScrapeRun(BaseModel):
    id: str                          # UUID
    bank: str                        # Bank that was scraped
    started_at: datetime
    finished_at: datetime | None
    status: str                      # "running", "success", "failed"
    promotions_found: int            # Total found in this run
    promotions_new: int              # Newly inserted
    promotions_updated: int          # Updated (checksum changed)
    error_message: str | None        # Error message (if failed)
```

#### `core/registry.py` — Adapter Registry

Adapters self-register via decorator:

```python
from card_retrieval.core.registry import register

@register("my_bank")
class MyBankAdapter(BaseAdapter):
    ...
```

Internally stored as a dict: `{"ktc": KtcAdapter, "cardx": CardxAdapter, ...}`

Functions:
- `register(name)` — decorator for registration
- `get_adapter(name)` — get adapter class by name
- `list_adapters()` — list all registered adapters

#### `core/base_adapter.py` — Abstract Base

Interface that all adapters must implement:

```python
class BaseAdapter(ABC):
    @abstractmethod
    def get_bank_name(self) -> str: ...         # Bank identifier

    @abstractmethod
    def get_source_url(self) -> str: ...        # Promotion page URL

    @abstractmethod
    async def fetch_promotions(self) -> list[Promotion]: ...  # Scrape data

    async def close(self) -> None: ...          # Cleanup (optional override)
```

#### `core/pipeline.py` — Orchestrator

Controls the execution flow:

1. Create `ScrapeRun` record (status=running)
2. Call `adapter.fetch_promotions()` to scrape data
3. Call `repo.upsert_promotions()` to store in DB
4. Call `repo.deactivate_missing()` to soft-delete promotions no longer on the site
5. Update `ScrapeRun` (status=success/failed)
6. Call `adapter.close()` to cleanup resources
7. Save `ScrapeRun` to DB
8. Check for repeated failures (3+ consecutive fails triggers critical log)

Errors are caught and recorded in `ScrapeRun.error_message` — the system never crashes entirely.

Supports `dry_run=True` mode: fetches and parses but skips all DB writes.

#### `core/exceptions.py` — Custom Exceptions

```
CardRetrievalError          # base
├── FetchError              # Failed to fetch data (HTTP error, timeout)
├── ParseError              # Failed to parse data (HTML structure changed)
├── AdapterError            # Error in adapter logic
└── StorageError            # Failed to write to DB
```

---

### 2. Adapters

#### KTC Adapter (`adapters/ktc/`)

**How it works:**

KTC uses Next.js (SSR) which embeds all data as JSON in a `<script id="__NEXT_DATA__">` tag. No browser needed — simple HTTP + JSON parsing.

```
1. HTTP GET https://www.ktc.co.th/promotion
2. Find <script id="__NEXT_DATA__"> in HTML
3. JSON.parse() and extract from props.pageProps.promotions
4. Convert each item to a Promotion object
5. Loop through 15 categories: dining-restaurants, shopping, air-ticket-hotels-travel, ...
6. Merge + deduplicate by source_id
```

**Fallback:** If `__NEXT_DATA__` is not present, falls back to HTML parsing via CSS selectors.

**Rate limit:** 2 seconds between requests (~32 seconds total for 16 pages)

#### CardX Adapter (`adapters/cardx/`)

**How it works:**

CardX is a Flutter web app (SPA) that renders everything client-side. No HTML to parse — must open a real browser and intercept API responses.

```
1. Launch Playwright Chromium browser
2. Set up response interceptor (capture responses matching URL patterns)
3. Navigate to https://www.cardx.co.th/credit-card/promotion
4. Wait for Flutter app to load and make API calls
5. Collect intercepted JSON responses
6. Parse JSON -> Promotion objects
```

**Rate limit:** 5 seconds between requests

#### Kasikorn Adapter (`adapters/kasikorn/`)

**How it works:**

Kasikorn has anti-bot protection that returns 403 for headless browsers. Must use stealth techniques and **headed mode**.

```
1. Launch Playwright in stealth mode (remove webdriver flags, fake plugins, set timezone)
2. Navigate to promotion page
3. Wait for .thumb-title elements to appear
4. Scroll page (simulate human behavior)
5. Extract rendered HTML
6. Parse with CSS selectors (.box-thumb, .thumb-title, .thumb-des, .thumb-date)
7. Parse Thai dates (e.g., "1 ม.ค. 67" -> 2024-01-01)
```

**Important:** Kasikorn blocks headless browsers (403). You must set `CARD_RETRIEVAL_BROWSER_HEADLESS=false` or use Xvfb on the server.

**Stealth Techniques:**
- Remove `navigator.webdriver` flag
- Fake `navigator.plugins` (5 plugins)
- Set timezone to `Asia/Bangkok`
- Set locale to `th-TH`
- Disable `AutomationControlled` blink feature
- Set `window.chrome = {runtime: {}}`
- Random delays between actions
- Smooth scrolling at 70% of viewport height

**Rate limit:** 10 seconds between requests

**Thai Date Parser** supports:
- `1 ม.ค. 67` -> 2024-01-01 (abbreviated Buddhist era)
- `1 มกราคม 2567` -> 2024-01-01 (full Buddhist era)
- `01/01/2024` -> 2024-01-01 (standard format)

---

### 3. Fetchers

#### `HttpFetcher` (`fetchers/http_fetcher.py`)

For sites that don't require a browser (e.g., KTC).

- Uses `httpx` async client with HTTP/2
- Headers mimic a Chrome browser (User-Agent, Accept-Language in Thai)
- Auto-retry 3 times with exponential backoff (2s, 4s, 8s)
- Follows redirects automatically
- 30-second timeout

#### `BrowserFetcher` (`fetchers/browser_fetcher.py`)

For SPAs that require JavaScript rendering (e.g., CardX).

- Uses Playwright Chromium
- Viewport: 1920x1080
- Two modes:
  - `fetch_with_intercept()` — navigate and capture API responses matching a pattern
  - `fetch_rendered_html()` — navigate and return fully rendered HTML

#### `StealthFetcher` (`fetchers/stealth_fetcher.py`)

For bot-protected sites (e.g., Kasikorn).

- Everything from `BrowserFetcher` plus:
  - Injects JavaScript on every page to remove automation fingerprints
  - `_human_like_delay()` — random delays between actions
  - `_scroll_page()` — smooth human-like scrolling

---

### 4. Storage Layer

#### `storage/database.py` — Database Connection

```python
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
```

Switch databases by changing `CARD_RETRIEVAL_DATABASE_URL`:
- SQLite: `sqlite:///data/promotions.db`
- PostgreSQL: `postgresql://user:pass@host:5432/dbname`

#### `storage/orm_models.py` — Table Definitions

**`promotions` table:**

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID |
| bank | VARCHAR(50) | indexed |
| source_id | VARCHAR(255) | unique with bank |
| source_url | VARCHAR(1024) | |
| title | VARCHAR(500) | |
| description | TEXT | |
| image_url | VARCHAR(1024) | nullable |
| card_types | JSON | list of strings |
| category | VARCHAR(100) | nullable |
| merchant_name | VARCHAR(255) | nullable |
| discount_type | VARCHAR(50) | nullable |
| discount_value | VARCHAR(100) | nullable |
| minimum_spend | FLOAT | nullable |
| start_date | DATE | nullable |
| end_date | DATE | nullable |
| terms_and_conditions | TEXT | nullable |
| raw_data | JSON | raw source data |
| checksum | VARCHAR(64) | SHA-256 |
| scraped_at | DATETIME | |
| is_active | BOOLEAN | default true, indexed |
| created_at | DATETIME | auto |
| updated_at | DATETIME | auto on update |

Constraints: `UNIQUE(bank, source_id)`, `INDEX(bank, source_id)`

**`scrape_runs` table:**

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID |
| bank | VARCHAR(50) | indexed |
| started_at | DATETIME | |
| finished_at | DATETIME | nullable |
| status | VARCHAR(20) | running/success/failed |
| promotions_found | INT | |
| promotions_new | INT | |
| promotions_updated | INT | |
| error_message | TEXT | nullable |

#### `storage/repository.py` — Data Access

**`upsert_promotions(promotions)`:**

1. Look up by `bank + source_id`
2. Not found -> INSERT (counted as new)
3. Found but checksum differs -> UPDATE (counted as updated)
4. Found and checksum matches -> skip (data unchanged)
5. Returns `(new_count, updated_count)`

**`deactivate_missing(bank, active_source_ids)`:**

Sets `is_active=False` for promotions belonging to `bank` that are not in the provided `active_source_ids` list. This soft-deletes promotions that have been removed from the bank's website.

---

### 5. Scheduling

#### `scheduling/scheduler.py`

Uses APScheduler (AsyncIOScheduler) with configurable intervals:

| Bank | Frequency | Reason |
|------|-----------|--------|
| KTC | Every 6 hours | HTTP-only, lightweight, frequently updated |
| CardX | Every 12 hours | Requires browser, moderate load |
| Kasikorn | Every 24 hours | Stealth browser is heavy, site updates infrequently |

---

### 6. Utilities

#### `utils/text.py` — Thai Text Processing

**`normalize_thai_text(text)`:**
- Removes zero-width characters (U+200B, U+200C, U+200D, U+FEFF) commonly hidden in Thai web content
- Collapses repeated whitespace to a single space
- Strips leading/trailing whitespace

**`extract_discount(text)`:**
Extracts discount type from Thai text:
- `"ส่วนลด 50%"` -> `("percentage", "50%")`
- `"รับเงินคืน 500 บาท"` -> `("cashback", "500 baht")`
- `"5 เท่า"` -> `("points", "5 points")`
- Priority: percentage -> points -> cashback/discount

**`extract_minimum_spend(text)`:**
Extracts minimum spend amount:
- `"ช้อปครบ 3,000 บาท"` -> `3000.0`
- `"ขั้นต่ำ 500 baht"` -> `500.0`
- Supported keywords: ครบ, ตั้งแต่, ขั้นต่ำ, minimum

#### `utils/rate_limiter.py` — Per-Domain Rate Limiting

Prevents excessive requests to any single domain:

```python
await rate_limiter.wait("ktc.co.th", 2.0)    # wait at least 2s since last request
await rate_limiter.wait("cardx.co.th", 5.0)   # wait at least 5s
```

Uses `asyncio.Lock` to prevent race conditions between concurrent requests.

---

## Data Schema

### Data Flow

```
Bank website (HTML/JSON)
    │
    v
Adapter.fetch_promotions()       <-- scrape + parse
    │
    v
list[Promotion]                  <-- Pydantic validated
    │
    v
Repository.upsert_promotions()   <-- deduplicate via checksum
    │
    v
Repository.deactivate_missing()  <-- soft-delete removed promotions
    │
    v
PromotionRow (SQLAlchemy)        <-- written to DB
    │
    v
PostgreSQL / SQLite
```

### Discount Types

| Type | Example | Meaning |
|------|---------|---------|
| `percentage` | 50% | Percentage discount |
| `cashback` | 500 baht | Cash back (requires "คืน" or "cashback" in text) |
| `discount` | 1000 baht | Fixed amount discount |
| `points` | 5000 points | Reward points/multiplier |

---

## Database

### Migrations (Alembic)

```bash
# Create a new migration
alembic revision --autogenerate -m "add new column"

# Run migrations
alembic upgrade head

# Check current migration
alembic current
```

### Example Queries

These queries work for both SQLite (local dev) and PostgreSQL (production):

```sql
-- Count promotions per bank
SELECT bank, COUNT(*) FROM promotions WHERE is_active = true GROUP BY bank;

-- Latest promotions
SELECT bank, title, discount_type, discount_value, end_date
FROM promotions
WHERE is_active = true
ORDER BY scraped_at DESC
LIMIT 10;

-- Scrape run history
SELECT bank, status, promotions_found, promotions_new, started_at
FROM scrape_runs
ORDER BY started_at DESC
LIMIT 10;
```

---

## Adding a New Bank

Example: adding SCB (Siam Commercial Bank).

### Step 1: Create the adapter directory

```
src/card_retrieval/adapters/scb/
├── __init__.py
├── constants.py
├── parser.py
└── adapter.py
```

### Step 2: Define constants

```python
# adapters/scb/constants.py
BASE_URL = "https://www.scb.co.th"
PROMOTION_URL = f"{BASE_URL}/th/personal-banking/credit-cards/promotions"
BANK_NAME = "scb"
RATE_LIMIT_SECONDS = 3.0
```

### Step 3: Write the parser

```python
# adapters/scb/parser.py
from card_retrieval.core.models import Promotion

def parse_promotions(data: dict) -> list[Promotion]:
    promotions = []
    for item in data.get("items", []):
        promotions.append(Promotion(
            bank="scb",
            source_id=str(item["id"]),
            source_url=f"https://www.scb.co.th/promotion/{item['slug']}",
            title=item["title"],
            description=item.get("description", ""),
            raw_data=item,
        ))
    return promotions
```

### Step 4: Write the adapter

```python
# adapters/scb/adapter.py
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.registry import register

@register("scb")                              # <-- this registers the adapter
class ScbAdapter(BaseAdapter):
    def get_bank_name(self) -> str:
        return "scb"

    def get_source_url(self) -> str:
        return "https://www.scb.co.th/.../promotions"

    async def fetch_promotions(self) -> list[Promotion]:
        # Choose the appropriate fetcher
        fetcher = HttpFetcher()               # or BrowserFetcher / StealthFetcher
        html = await fetcher.fetch(self.get_source_url())
        return parse_promotions(html)

    async def close(self):
        await self._fetcher.close()
```

### Step 5: Import in `adapters/__init__.py`

```python
from card_retrieval.adapters.scb import adapter as _scb  # noqa: F401
```

### Step 6: Test

```bash
card-retrieval list-adapters          # should show scb
card-retrieval run --bank scb         # test scraping
```

**No changes needed to the pipeline, CLI, scheduler, or other adapters.**

---

## Testing

### Run tests

```bash
# All tests
pytest tests/ -v

# Adapter tests only
pytest tests/adapters/ -v

# With coverage report
pytest tests/ --cov=card_retrieval --cov-report=html
```

### Test Suite (28 tests)

| Test File | Count | What it tests |
|-----------|-------|---------------|
| `test_models.py` | 4 | Checksum determinism, change detection, defaults, dates |
| `test_registry.py` | 3 | Register, get, list adapters |
| `test_repository.py` | 5 | Upsert new, dedup, update on change, query, scrape runs |
| `test_text_utils.py` | 6 | Thai text normalize, discount extraction, minimum spend |
| `test_ktc_parser.py` | 4 | `__NEXT_DATA__` extraction, JSON parse, HTML fallback |
| `test_cardx_parser.py` | 3 | API response parse, empty, malformed |
| `test_kasikorn_parser.py` | 2 | HTML parse + Thai date, empty HTML |
| **Total** | **28** | **All passing** |

All tests use saved fixtures (HTML/JSON) in `tests/fixtures/` — no live network access required.

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

---

## Deployment

### Docker Compose

The production setup runs two services:

```yaml
services:
  scraper:
    build: .
    environment:
      - CARD_RETRIEVAL_DATABASE_URL=${CARD_RETRIEVAL_DATABASE_URL}
      - CARD_RETRIEVAL_BROWSER_HEADLESS=false
    entrypoint: ["/app/entrypoint.sh"]
    restart: unless-stopped

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CARD_RETRIEVAL_DATABASE_URL=${CARD_RETRIEVAL_DATABASE_URL}
      - CARD_RETRIEVAL_API_KEYS=${CARD_RETRIEVAL_API_KEYS}
    command: ["serve"]
    restart: unless-stopped
```

- **scraper** — runs `entrypoint.sh` which executes Alembic migrations then starts the scheduler with `xvfb-run` (for headed Kasikorn scraping)
- **api** — runs `card-retrieval serve` on port 8000

```bash
# Build and start both services
docker compose up -d --build

# View logs
docker compose logs -f

# Restart just the API
docker compose restart api
```

### Important: Kasikorn requires headed mode

Kasikorn blocks headless browsers (returns 403). On a server, you need a virtual display:

```bash
# In Dockerfile or server setup, use xvfb-run:
xvfb-run card-retrieval run --bank kasikorn

# Or set the env var:
CARD_RETRIEVAL_BROWSER_HEADLESS=false
```

The Playwright Docker base image (`mcr.microsoft.com/playwright/python`) includes Xvfb.

### Deployment Platforms

| Platform | Cost/month | RAM | Best for |
|----------|-----------|-----|----------|
| **DigitalOcean Droplet** | $12 (~420 THB) | 2GB | Recommended — enough for Playwright+Chromium |
| **Hetzner CX22** | ~$4 (~150 THB) | 4GB | Cheapest always-on option |
| **Railway** | ~$5 | 512MB-2GB | Easiest setup, but RAM may be tight |
| **Fly.io** | ~$3-5 | 1GB+ | Good alternative PaaS |
| **GCP Cloud Run** | ~$0-2 | Configurable | Cheapest if running infrequently |

### Production Configuration

```bash
# Use PostgreSQL instead of SQLite
export CARD_RETRIEVAL_DATABASE_URL="postgresql://user:pass@localhost:5432/card_promo"

# Set API keys for the REST API
export CARD_RETRIEVAL_API_KEYS="your-production-key"

# Enable JSON logging
export CARD_RETRIEVAL_LOG_JSON="true"

# Run Alembic migration
alembic upgrade head

# Install Playwright browser deps (Linux)
playwright install --with-deps chromium

# Health check
curl http://localhost:8000/api/v1/health
```
