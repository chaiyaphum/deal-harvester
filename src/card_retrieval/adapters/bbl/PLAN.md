# Bangkok Bank (BBL) adapter — implementation plan

Status: **scaffold only** (2026-04-22). Adapter is registered so `list-adapters`
surfaces it, but `fetch_promotions` raises `NotImplementedError`.

## Site structure

- Root: https://www.bangkokbank.com/
- Credit-card promotions hub (verify on first fetch):
  `https://www.bangkokbank.com/th/personal/other-services/promotions/credit-card-promotions`
- Alternative paths observed historically:
  - `/th/personal/own-a-card/promotion`
  - `/SiteCollectionDocuments/promotions/` (SharePoint-style CMS legacy)
- BBL runs on Sitecore (ASP.NET) with substantial server-side rendering, but the
  promo grid may hydrate via a `/api/sitecore/` XHR call — confirm during
  implementation.

## Fetcher choice

**HttpFetcher + BeautifulSoup** is the first candidate:

- Historical inspection shows server-rendered cards with stable class names like
  `promotion-item`, `card-promotion`, `teaser-promo`.
- If the grid turns out to be XHR-hydrated, switch to BrowserFetcher with
  `fetch_rendered_html` (wait for the card selector) or `fetch_with_intercept`
  (capture the Sitecore API JSON).
- No Cloudflare / Akamai observed on BBL as of 2026-04-22, so StealthFetcher is
  unlikely to be needed. Revisit if a 403 appears.

## Expected row count

- 40-70 active promotions. BBL categorizes into: dining, travel, shopping,
  entertainment, online, installment. Single-page fetch should ship all of them;
  if paginated, follow the "load more" pattern via BrowserFetcher scroll.

## Anti-bot observations

- Standard ASP.NET Sitecore — no known anti-bot layer.
- `robots.txt` does not disallow the promotions path.
- Some PDFs linked from promo pages require a referer header — not relevant for
  the listing scrape.

## Test-fixture strategy

- Capture a trimmed HTML fixture (~60 KB) of the promotion hub:
  `tests/fixtures/bbl_promotions.html`.
- Test file: `tests/adapters/test_bbl_parser.py`, mirroring the Krungsri tests.
- BBL's date format is usually Thai Buddhist Era with month names spelled in full
  (e.g., `1 มกราคม 2569 ถึง 31 มีนาคม 2569`). The Thai-date helper already built
  in Krungsri / Kasikorn parsers can be reused — consider promoting it to
  `utils/date.py` before adding BBL (note: still scoped, do not do it
  preemptively).

## Estimated effort

- Parser + constants + tests: **4-6 hours** once live HTML fixture is captured.
- Fetcher decision gate: **1 hour**.
- Total: **~1 working day**.

## Next steps (when promoted to active work)

1. Fetch live HTML, save trimmed fixture.
2. Identify stable card selector in the DOM.
3. Build `parse_promotions_from_html` — reuse the Thai-date helper, the "ที่" /
   "ร่วมกับ" merchant heuristic, and the `extract_discount` util.
4. Replace `NotImplementedError` with a fetch/parse/dedupe body matching the
   Krungsri adapter shape.
5. Add `test_bbl_parser.py`. Run ruff + pytest before commit.
