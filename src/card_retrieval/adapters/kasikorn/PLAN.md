# Kasikornbank (KBank) adapter — implementation plan

Status: **live** (2026-03), with heuristic tuning ongoing. See Decision log
at the end of this file for dated changes.

## What ships today

- **Fetcher:** `StealthFetcher` (Playwright + stealth shim). Kasikorn's edge
  returns HTTP 403 to every headless-browser signature we've tested; even the
  bundled Chromium fails without an Xvfb display. The `api` container's
  entrypoint now gates on the Xvfb socket (`/tmp/.X11-unix/X99`) before
  booting uvicorn — see `docker-compose.yml` (fix landed 2026-04-22).
- **PROMOTION_URL:** `/th/promotion/creditcard/Pages/index.aspx` (listing
  hub). Detail pages (`/th/promotion/creditcard/pages/<slug>.aspx`) are
  linked per-tile but **not** crawled today — see
  `docs/DESIGN_CARD_TYPES.md` for the detail-crawl design.
- **Selectors:** `.box-thumb` wraps each card; `.thumb-title`, `.img-thumb
  img`, `a.img-thumb`, `.thumb-date`, `.promo-item dt`, `.thumb-des`.
- **URL resolution:** `urljoin(PROMOTION_URL, href)` so the tile's
  `"../pages/foo.aspx"` relative paths resolve to absolute URLs without the
  `kasikornbank.com..` concatenation bug that shipped in the 2026-03 cut
  (fixed 2026-04-22, commit `4f6df29`).
- **Dates:** Thai short-form (`1 ม.ค. 67 - 31 มี.ค. 67`) with BE→CE
  conversion via `THAI_MONTHS` map + 2-digit-year normalisation.
- **Merchant extraction:** heuristic regex — see next section.
- **Card types:** `card_types=[]` on every row (listing tiles have no
  coverage data). Implementing this requires the detail-page crawl
  described in `docs/DESIGN_CARD_TYPES.md`. **Not in scope for this branch.**

## Merchant-name heuristic (2026-04-24 update)

The listing tile only exposes a title + a short description. Merchant name
must be recovered from free text. Patterns, in order of precedence:

1. `"ที่ <MERCHANT>"` — "at <MERCHANT>" (~60% of KBank titles)
2. `"ร่วมกับ <MERCHANT>"` — "together with <MERCHANT>"
3. `"จาก <MERCHANT>"` — "from <MERCHANT>" (gift/voucher promos) **[added]**
4. `"กับ <MERCHANT>"` — bare "with <MERCHANT>" with `(?<!ร่วม)` lookbehind so
   it doesn't double-match "ร่วมกับ" **[added]**
5. `"@ <MERCHANT>"` — brand-tag shorthand **[added]**
6. ALL-CAPS English prefix (e.g. `ASB GREEN VALLEY ผ่อน 0%…`)

Each capture uses a shared `_TRAILER` lookahead that stops at the first
terminator seen on live titles: digits, `ใช้จ่าย`, `รับ`, `ครบ`, `เมื่อ`,
`ใน`, `ของ`, `ตั้งแต่`, `วันที่`, `สาขา`, `ผ่อน`, `นาน`, an en-dash, or
end-of-string. The `_MERCHANT_BLOCKLIST` rejects obvious false positives
(`บัตรเครดิต`, `KBank`, `กสิกรไทย`, `เครดิตเงินคืน`, `ร้านค้า`, …).

Unit tests cover each pattern — see `tests/adapters/test_kasikorn_parser.py`.

## Known gaps

- `merchant_name` still null on promos whose title names the benefit before
  the merchant (e.g. `"รับเครดิตเงินคืน 10% เมื่อใช้จ่ายครบ 10,000 บาท"`).
  These are genuinely merchant-less promos and correctly return `None`.
- `card_types=[]` — tracked in `docs/DESIGN_CARD_TYPES.md`; blocked on
  founder approval (+16 min per scheduler run, 10s rate limit × 30 detail
  pages).
- Manual `POST /api/v1/scrape/trigger` frequently times out at the nginx
  edge because the stealth fetch can exceed 60s. The scheduler's
  in-container run succeeds. Don't loop-trigger in production;
  the scheduler's 6-hour cadence (see `scheduling/config.py`) is the
  intended trigger path.

## Decision log

- **2026-03-19** — last successful scheduler run before the KTC/Kasikorn
  pipeline went stale (memory: `project_deal_harvester_gaps.md`).
- **2026-04-22** — Xvfb readiness loop added to `docker-compose.yml` api
  entrypoint. URL-concat bug fixed. First merchant-name heuristic shipped
  (commit `4f6df29`).
- **2026-04-22 late-PM** — `Promotion.checksum` widened to include every
  render-critical field (commit `05d1281`) so that a re-scrape with the new
  merchant heuristic triggers an upsert instead of a no-op.
- **2026-04-24** — merchant heuristic widened (`จาก`, bare `กับ`, `@`
  patterns + trailer lookahead). Tests: `tests/adapters/test_kasikorn_parser.py`
  (14 total, 6 new on this branch). Detail-page crawl still deferred.
