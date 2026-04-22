# UOB Thailand adapter — implementation plan

Status: **scaffold only** (2026-04-22). Adapter is registered so `list-adapters`
surfaces it, but `fetch_promotions` raises `NotImplementedError`.

## Site structure

- Root: https://www.uob.co.th/
- Credit-card promotions hub (verify on first fetch — UOB restructures occasionally):
  `https://www.uob.co.th/personal/cards/promotions/all-promotions.page`
- Alternative hubs observed in the past: `/personal/cards/credit-card/promotions.page`
  and `/web-resources/uobth/.../promotions.json`. Check both before committing
  the final `PROMOTION_URL`.
- Server-rendered HTML wrapped in an AEM (Adobe Experience Manager) template.
  Most card-listing components emit a repeating block with class hints like
  `promo-card`, `promotion-item`, `card-listing__item`. Thumbnails live inside
  `<img>` tags with a `src` attribute (occasionally `data-src` for lazy-loaded).
- Category filter appears to be client-side only (no per-category URL changes
  observed), so a single fetch of the hub should suffice.

## Fetcher choice

**HttpFetcher + BeautifulSoup** is the correct first choice:

- Page is server-rendered HTML (AEM), not an SPA — confirmed by `view-source`
  showing the promo list inline.
- Cloudflare is NOT in front of the promotion hub as of 2026-04-22; a plain
  httpx GET with the existing default User-Agent should succeed.
- If UOB ships an anti-bot check later, escalate to BrowserFetcher first, then
  StealthFetcher (the Kasikorn pattern) only if BrowserFetcher is 403'd.

## Expected row count

- 30-60 active card promotions at any given time (based on 2026-03 manual count).
- Pagination: scroll-loaded "load more" button — may need BrowserFetcher scroll
  loop if the first HTML response only ships the first page.

## Anti-bot observations

- No Cloudflare challenge observed 2026-04-22.
- `robots.txt` does not disallow `/personal/cards/promotions/*`.
- Rate limit: 4.0s between requests is conservative and matches the CardX cadence.

## Test-fixture strategy

- Capture a real HTML fixture (~50-80 KB trimmed) during the first implementation
  session: `curl -A "<default-ua>" <PROMOTION_URL> > tests/fixtures/uob_promotions.html`.
- Build `tests/adapters/test_uob_parser.py` mirroring `test_krungsri_parser.py`:
  3-4 promo assertions (title, source_url, image_url, category, merchant where
  the Thai "ที่" / "ร่วมกับ" hint is present, date range).
- UOB often uses Western-calendar ISO dates (`YYYY-MM-DD` or `DD MMM YYYY`)
  rather than Thai BE dates — plan for both parsers.

## Estimated effort

- Parser + constants + tests: **4-6 hours** once a live HTML fixture is captured.
- Fetcher decision gate: **1 hour** (curl + inspect + pick HttpFetcher vs Browser).
- Total: **~1 working day** for a clean UOB adapter, assuming no Cloudflare surprise.

## Next steps (when promoted to active work)

1. Fetch live HTML, save trimmed fixture.
2. Inspect DOM for stable card selector.
3. Build `parser.py` using `parse_promotions_from_html` signature (matches
   Krungsri / Kasikorn) so the adapter's `fetch_promotions` can call it directly.
4. Replace the `NotImplementedError` in `adapter.py` with the same shape as the
   Krungsri adapter (fetch -> parse -> dedupe -> log).
5. Add `test_uob_parser.py`. Wire up ruff + pytest before commit.
