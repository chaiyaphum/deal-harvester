# Amex Thailand adapter — implementation plan

Status: **scaffold only** (2026-04-22). Adapter is registered so `list-adapters`
surfaces it, but `fetch_promotions` raises `NotImplementedError`.

## Site structure

- Root: https://www.americanexpress.com/th/
- Likely promotion hubs (verify — Amex rotates content between these):
  - `https://www.americanexpress.com/th/benefits/offers/` (card-member offers hub)
  - `https://www.americanexpress.com/th/credit-cards/benefits/` (card-feature pages)
- Architecture: heavily JS-driven. The page HTML is shipped with a thin React
  shell; promo tiles are injected client-side from a JSON API hit at
  `api/content/...` or `axp-offers/...`. Confirm via DevTools network tab.
- Login wall: many offers are gated behind card-member login. Plan to scrape the
  **public** "offers for prospects" tier first — Amex shows 10-30 promos without
  a login.

## Fetcher choice

**BrowserFetcher with `fetch_with_intercept`** is the recommended first attempt:

- Plain httpx GET returns a near-empty React shell — confirmed 2026-04-22.
- The CardX adapter already demonstrates the intercept pattern for an SPA
  that loads promos via XHR. Copy that structure: capture JSON responses
  matching `axp-offers`, `api/content`, or `/offers/` URL patterns, then parse
  from the captured JSON.
- If BrowserFetcher is blocked by Amex's anti-bot (Akamai Bot Manager is
  commonly deployed on americanexpress.com), escalate to StealthFetcher.
- StealthFetcher with `pre_visit_url=BASE_URL` to warm cookies may be required
  from day one — note Amex uses geolocation + IP reputation checks.

## Expected row count

- 10-30 public-facing offers at any time. Member-only tier adds ~50 more but
  requires auth (out of scope for MVP).

## Anti-bot observations

- Akamai Bot Manager almost certainly in front of the page. Expect:
  - `_abck` and `bm_sz` cookies set on first visit.
  - Request body fingerprinting for POST calls to the offers API.
- Mitigations: StealthFetcher + human-like scroll + 6s rate limit.
- If blocked, fall back to fetching the HTML of `/th/benefits/offers/` directly
  with a real browser session cookie captured manually, then parse the
  server-rendered subset (~10 offers visible without JS).

## Test-fixture strategy

- Two fixture files needed:
  - `tests/fixtures/amex_offers_api.json` — captured JSON from the intercept.
  - `tests/fixtures/amex_offers.html` — optional fallback for server-rendered
    parsing if the API path is too heavily protected.
- Test mirrors `test_cardx_parser.py` shape: feed the captured JSON into the
  parser, assert 2-3 promos with merchant, discount_type, date range.
- Amex uses Western-calendar dates (`DD MMM YYYY`), no Thai BE — simpler date
  parsing than Krungsri/Kasikorn.

## Estimated effort

- Fetcher decision + live capture: **4-6 hours** (Akamai churn is the risk).
- Parser + tests: **6-8 hours**.
- Total: **~2 working days** given the anti-bot uncertainty. This is the
  highest-risk adapter in Phase 2.

## Next steps (when promoted to active work)

1. Open DevTools on the live hub, identify the offers API endpoint.
2. Try plain BrowserFetcher intercept first. If 403, swap to StealthFetcher.
3. Capture a real API response into `tests/fixtures/amex_offers_api.json`.
4. Build `parse_intercepted_data` (CardX signature) in `parser.py`.
5. Wire up adapter `fetch_promotions` to the CardX pattern (loop over intercept
   patterns, dedupe, log).
6. Add `test_amex_parser.py`. Run ruff + pytest before commit.
