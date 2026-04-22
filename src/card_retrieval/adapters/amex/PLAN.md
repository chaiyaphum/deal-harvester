# Amex Thailand adapter — implementation plan

Status: **implemented (dining category)** (2026-04-22). `fetch_promotions`
returns a deduplicated list of `Promotion` objects parsed from the live hub.
Live-captured HTML fixture ships in `tests/fixtures/amex_offers.html` (8 of
45 dining offers, trimmed).

## What actually shipped

- **Fetcher:** `StealthFetcher.fetch_rendered_html` with a `pre_visit_url`
  pointing at `/th/`. This is required. Observed 2026-04-22:
  - Plain `httpx` → `RemoteProtocolError` (TLS stream reset immediately
    after SNI). Same for `curl`: HTTP/2 `INTERNAL_ERROR`.
  - `BrowserFetcher.fetch_rendered_html` cold (no pre-visit) → Playwright
    navigation timeout at 30 s. Akamai Bot Manager slow-walks the request.
  - `StealthFetcher` with pre-visit to `/th/` → 200 OK, 1.0 MB of rendered
    HTML, 45 `div.offer.parbase` tiles. The root sets `_abck` and `bm_sz`
    cookies that the subsequent navigation presents, passing the bot check.
- **PROMOTION_URL:** `/th-th/benefits/promotions/dining.html`. The historical
  `/th/benefits/offers/` path returns a custom "ไม่พบหน้า" (not found) page.
  `/th/` is the Thai landing page and legitimately links to
  `/th-th/benefits/promotions/dining.html`.
- **Selectors:** `.offer.parbase` wraps each tile. Inside every tile:
  `.offer-header > p` (title), `.offer-desc` (description), `.offer-dates`
  (date range prefixed with "ระยะเวลา:"), `img.card-detail-image` (image),
  `a.link-underlined` (image wrap link to detail page). 45 of 45 tiles in
  the captured HTML parse cleanly.
- **Date parsing:** Amex uses Western-calendar `DD/MM/YYYY`. A dedicated
  `_parse_amex_date_range` strips the "ระยะเวลา:" prefix, splits on
  `-`/`–`/`ถึง`, then tries DD/MM/YYYY, DD-MM-YYYY, ISO, `DD MMM YYYY`, and
  `DD MMMM YYYY` formats.
- **Merchant extraction:** Shared Thai preposition heuristic with one Amex
  twist — if no "ที่" / "ร่วมกับ" hint matches and the title is ≤80 chars,
  the title itself is used as the merchant (Amex tiles typically ARE the
  venue name). Longer titles (full-sentence descriptions that happen to sit
  in the `<p>` slot) return `None` to avoid polluting merchant search.
  Blocklist suppresses Amex brand names (Amex, American Express, Platinum,
  อเมริกัน) and Thai month names.
- **Category:** hard-coded to `"dining"` since this parser is wired to the
  dining hub only. Walking travel/lifestyle/explore-asia is a clean
  extension (same DOM shape).

## Anti-bot notes

- Akamai Bot Manager IS active. Without stealth warm-up it blocks.
- `StealthFetcher` already injects the anti-webdriver script + launches with
  `--disable-blink-features=AutomationControlled`. That plus the pre-visit is
  enough as of 2026-04-22. If Amex tightens, the next escalation is to
  randomize viewport/UA per session and add a longer human-like delay after
  the pre-visit (not needed today).
- Rate limit: 6 s between requests (twice UOB's rate). Amex's bot manager
  logs request velocity per source IP, so we stay conservative.

## Tests

- `tests/adapters/test_amex_parser.py` — 9 tests, all green:
  - parses 8 cards out of the live fixture
  - categories and absolute URLs verified
  - dates parse as `(2026-04-01, 2026-09-30)` from `"ระยะเวลา: 01/04/2026 - 30/09/2026"`
  - source_id strips `.html`; relative `dining.foo.html` hrefs resolve to absolute
  - image URLs resolve against BASE_URL
  - empty HTML → `[]`
  - `_parse_amex_date_range` with/without "ระยะเวลา:" prefix + invalid input
  - merchant-extraction: `ที่` heuristic, short-title fallback, blocklist

## Expected row count

- 45 dining offers as of 2026-04-22. Other categories add roughly:
  - travel: ~20–30
  - lifestyle: ~15–25
  - explore-asia: ~10–20
  - **Total Amex TH:** ~90–120 offers when all four hubs are wired up.

## Follow-ups (not blockers)

1. Loop over the four category URLs in `AmexAdapter.fetch_promotions` and
   stamp the appropriate `category` per hub (currently hard-coded `"dining"`
   in the parser — move to adapter-driven or pass-through).
2. Persist `offer-dates` text verbatim in `raw_data` so downstream consumers
   can reason about "live now" vs "starts soon" without re-parsing.
3. If Akamai starts gating `StealthFetcher` too, the next step is
   [playwright-extra](https://github.com/berstend/puppeteer-extra-plugin-stealth)
   via a wrapper process, or a paid scraping API. Not needed today.
