# Deal Harvester — Development Log

> Repo: https://github.com/chaiyaphum/deal-harvester (private)
> Branch: `main`

---

## Session 2: 2026-03-18 — P1-P5 Implementation (Production-Ready)

### What was accomplished

Implemented Priorities 1-5: bug fixes, live testing against real websites, Alembic migration, robustness improvements, and Docker deployment files. The project is now production-ready.

**Commit:** `3847c3d`

### Priority 1: Bug Fixes & Lint (0 errors)

| Fix | File | Details |
|-----|------|---------|
| `settings` import bug | `main.py` | Moved import before usage in `schedule()` — was causing `NameError` |
| Import sorting (I001 x6) | Multiple | Auto-fixed with `ruff check --fix` |
| Line too long (E501 x2) | `config.py`, `repository.py` | Extracted variable, broke function signature |
| THAI_MONTHS naming (N806) | `kasikorn/parser.py` | Moved from function-local to module-level constant |
| UP045 suppression | `pyproject.toml` | Added per-file-ignore for typer `Optional` compatibility |
| UniqueConstraint | `orm_models.py` | Added `UNIQUE(bank, source_id)` + composite index |

### Priority 2: Live Testing Results

| Bank | Promotions | Changes Made |
|------|-----------|-------------|
| **KTC** | 160 | Updated category slugs: 15 new categories (old ones like `entertainment`, `gas-station` returned 404) |
| **CardX** | 14 | Worked as-is, API interception captured 8 responses |
| **Kasikorn** | 49 | URL changed to `/th/promotion/creditcard/Pages/index.aspx`, selectors updated to `.box-thumb/.thumb-title/.thumb-des/.thumb-date` |

**Key findings:**
- KTC categories changed significantly — updated from 10 to 15 slugs
- Kasikorn's old promotion URL (`/th/personal/card/credit-card/pages/promotions.aspx`) now returns a 404 page
- **Kasikorn blocks headless browsers** with 403 — must use headed mode (`CARD_RETRIEVAL_BROWSER_HEADLESS=false`) or Xvfb on servers
- Dedup verified for all 3 adapters (second run: `new=0, updated=0`)
- Updated test fixtures and assertions for new Kasikorn HTML structure

### Priority 3: Alembic Migration

- Updated `alembic/env.py` to use `settings.database_url` dynamically (instead of hardcoded in `alembic.ini`)
- Added `render_as_batch=True` for SQLite compatibility
- Generated initial migration: `c8934ac349bf_initial_schema_with_unique_constraint.py`
- Verified migration creates correct schema with UNIQUE constraint and indexes

### Priority 4: Robustness

| Feature | Details |
|---------|---------|
| `asyncio` fix | Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in scheduler, `asyncio.run()` pattern in CLI |
| `--dry-run` flag | `card-retrieval run --bank ktc --dry-run` — fetches and parses but skips all DB writes |
| Soft-delete | `repo.deactivate_missing(bank, active_source_ids)` — sets `is_active=False` for promotions no longer on the site |
| Repeated failure alerting | After a failed scrape, checks last 3 runs — if all failed, emits `log.critical("adapter_repeated_failure")` |

### Priority 5: Deployment

Created:
- `Dockerfile` — based on `mcr.microsoft.com/playwright/python:v1.50.0-noble`, installs uv + deps + Chromium
- `.dockerignore` — excludes `.venv/`, `.git/`, `data/*.db`, `.env`
- `docker-compose.yml` — `scraper` service with volume mount for `./data`
- `entrypoint.sh` — runs `init-db` -> `alembic upgrade head` -> `schedule`

### Final state

- **Lint:** 0 errors (`ruff check src/ tests/`)
- **Tests:** 28/28 passing
- **Live tested:** All 3 adapters scraping real data
- **Docker:** Build-ready

---

## Session 1: 2026-03-06 — Project Bootstrap

### What was accomplished

Built the entire project from an empty directory to a fully scaffolded, tested, and documented system. All Phase 1 items from the implementation plan are complete.

**Commit:** `1b59512`

**Stats:**
- 55 files created
- ~1,500 lines of application code (35 `.py` files under `src/`)
- ~630 lines of test code (7 test files, 28 tests)
- ~1,100 lines of documentation (README.md)
- All 28 tests passing

### Components built

| Component | Files |
|-----------|-------|
| Project scaffolding (pyproject.toml, uv, ruff, mypy) | `pyproject.toml` |
| Pydantic models (Promotion, ScrapeRun) | `core/models.py` |
| Adapter registry (decorator-based auto-discovery) | `core/registry.py` |
| Base adapter (abstract class) | `core/base_adapter.py` |
| Pipeline orchestrator (fetch -> store -> audit) | `core/pipeline.py` |
| Custom exceptions | `core/exceptions.py` |
| Configuration (env vars via pydantic-settings) | `config.py` |
| HTTP fetcher (httpx, HTTP/2, retry) | `fetchers/http_fetcher.py` |
| Browser fetcher (Playwright, API intercept) | `fetchers/browser_fetcher.py` |
| Stealth fetcher (Playwright, anti-bot) | `fetchers/stealth_fetcher.py` |
| KTC adapter (HTTP + __NEXT_DATA__ JSON) | `adapters/ktc/` |
| CardX adapter (Playwright API intercept) | `adapters/cardx/` |
| Kasikorn adapter (stealth browser) | `adapters/kasikorn/` |
| SQLAlchemy ORM models | `storage/orm_models.py` |
| Repository (upsert + checksum dedup) | `storage/repository.py` |
| Database connection | `storage/database.py` |
| Scheduler (APScheduler) | `scheduling/scheduler.py` |
| CLI (typer, 6 commands) | `main.py` |
| Thai text utils (normalize, extract discount) | `utils/text.py` |
| Rate limiter (per-domain, async) | `utils/rate_limiter.py` |
| Alembic migration setup | `alembic/` |
| Unit tests (28 tests, fixtures) | `tests/` |
| README documentation | `README.md` |

### Technical decisions

1. **`uv` over `pip`/`poetry`**: Fastest package manager, resolves deps in <1s
2. **Python 3.11 via uv**: System Python was 3.9.6, used `uv venv --python 3.11`
3. **`httpx[http2]` for KTC**: Next.js SSR with `__NEXT_DATA__` JSON — no browser needed
4. **Playwright over Selenium**: Better API, built-in response interception (critical for CardX), native async
5. **Stealth fetcher for Kasikorn**: KBank returns 403 for standard bots — stealth patches `navigator.webdriver`, fakes plugins, uses random delays
6. **Registry pattern with decorator**: `@register("bank_name")` auto-registers — adding a new bank requires zero pipeline/CLI changes
7. **Checksum-based deduplication**: SHA-256 of key fields enables idempotent re-runs
8. **SQLite for Phase 1**: Zero-config, switchable to PostgreSQL via env var
9. **`structlog`**: Structured key-value logging for production observability
10. **Discount extraction priority**: percentage -> points -> cashback (avoids false matches on spend amounts)

---

## Environment

| Item | Value |
|------|-------|
| Machine | macOS Darwin 25.3.0, Apple Silicon (aarch64) |
| Project Python | 3.11.15 (installed via uv) |
| Package manager | uv |
| Key deps | SQLAlchemy 2.0, Playwright 1.58, httpx 0.28, pydantic 2.12 |
| Database | SQLite at `data/promotions.db` |
| Git remote | `https://github.com/chaiyaphum/deal-harvester.git` |

---

## Phase 2 Backlog

- [ ] REST API (FastAPI) to serve promotion data
- [ ] LLM-powered parsing for unstructured terms & conditions
- [ ] Proxy rotation for Kasikorn (if stealth alone isn't enough)
- [ ] CI/CD pipeline (GitHub Actions: lint + test on push)
- [ ] Monitoring dashboard (promotion counts, scrape success rates)
- [ ] More bank adapters (SCB, Krungsri, Bangkok Bank, Citi, UOB)
