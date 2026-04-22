# Amex Thailand adapter — implementation plan

Status: **implemented (all four hubs)** (2026-04-22). `fetch_promotions`
returns a deduplicated list of `Promotion` objects parsed from the four live
category hubs (dining, travel, lifestyle, explore-asia). Live-captured HTML
fixtures ship in `tests/fixtures/amex_offers.html` (8 of 45 dining),
`tests/fixtures/amex_travel.html` (6 of 13), and
`tests/fixtures/amex_lifestyle.html` (6 of 20).

## What shipped

- **Fetcher:** `StealthFetcher.fetch_rendered_html` with a `pre_visit_url`
  pointing at `/th/`. Required. Observed 2026-04-22:
  - Plain `httpx` → `RemoteProtocolError` (TLS stream reset immediately
    after SNI). Same for `curl`: HTTP/2 `INTERNAL_ERROR`.
  - `BrowserFetcher.fetch_rendered_html` cold (no pre-visit) → Playwright
    navigation timeout at 30 s. Akamai Bot Manager slow-walks the request.
  - `StealthFetcher` with pre-visit to `/th/` → 200 OK, ~1.0 MB of rendered
    HTML per hub. The root sets `_abck` and `bm_sz` cookies that all four
    subsequent hub navigations reuse, passing the bot check.
- **Hub iteration:** `PROMOTION_HUBS` in `constants.py` lists the four
  category URLs. `fetch_promotions` warms the Akamai context exactly once
  (on the first hub), then loops through all four behind the 6 s rate
  limit. Dedup by `source_id` across hubs (occasional cross-listing).
- **Per-hub category map** (`HUB_CATEGORY_MAP`):

  | Hub slug       | `Promotion.category` | Notes                           |
  | -------------- | -------------------- | ------------------------------- |
  | `dining`       | `dining`             | Direct                          |
  | `travel`       | `travel`             | Direct                          |
  | `lifestyle`    | `shopping`           | Hub dominated by retail/beauty  |
  | `explore-asia` | `travel`             | Regional travel benefits        |

- **Expected tile counts (2026-04-22):**
  - dining: 45
  - lifestyle: 20
  - travel: 13
  - explore-asia: 8
  - **Total (deduped):** ~80–90 offers across all four hubs.
- **Selectors:** `.offer.parbase` wraps each tile. Inside every tile:
  `.offer-header > p` (title), `.offer-desc` (description), `.offer-dates`
  (date range prefixed with "ระยะเวลา:"), `img.card-detail-image` (image),
  `a.link-underlined` (image wrap link to detail page). Verified across
  all four hubs 2026-04-22.
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
- **Relative href resolution:** Per-hub `hub_url` is now threaded into the
  parser. A travel-hub href like `travel.foo.html` resolves against the
  travel URL, not dining. Back-compat: `parse_promotions_from_html(html)`
  (no kwargs) still defaults to `category="dining"` and dining hub_url.

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

- `tests/adapters/test_amex_parser.py` — 14 tests, all green:
  - dining fixture: 8 tiles, category="dining", date/source_id/image_url checks
  - travel fixture: 6 tiles, category="travel", all source_ids start `travel.`,
    30%/40% discounts detected
  - lifestyle fixture: 6 tiles, category="shopping", source_ids start `lifestyle.`
  - `HUB_CATEGORY_MAP` covers every slug in `PROMOTION_HUBS`
  - Relative href (`dining.foo.html`, `travel.foo.html`) resolves against the
    right hub_url
  - Date parser with/without "ระยะเวลา:" prefix + invalid input
  - Merchant extraction: `ที่` heuristic, short-title fallback, blocklist
  - Empty HTML → `[]`

## Follow-ups (not blockers)

1. **Persist raw offer-dates** in `raw_data` so downstream consumers can
   reason about "live now" vs "starts soon" without re-parsing.
2. **Explore-asia fixture:** currently only two fixtures (travel +
   lifestyle) added on top of dining. Explore-asia has the smallest tile
   count (8) and a similar DOM; adding a fixture is optional but would
   lock the category→"travel" mapping behind a test.
3. If Akamai starts gating `StealthFetcher` too, the next step is
   [playwright-extra](https://github.com/berstend/puppeteer-extra-plugin-stealth)
   via a wrapper process, or a paid scraping API. Not needed today.
