# Bangkok Bank (BBL) adapter — implementation plan

Status: **partially implemented** (2026-04-22). Fetcher + parser are working
end-to-end; the limitation is BBL-side catalog thinness and a broken TH
locale. The live EN hub surfaced only 1 promotion tile on the day this was
implemented; the fixture combines that live tile with 2 synthetic tiles to
exercise the full DOM shape.

## What actually shipped

- **Fetcher:** `BrowserFetcher.fetch_rendered_html`. Plain `httpx` and `curl`
  both fail on BBL with a TLS stream reset (`httpx.RemoteProtocolError:
  <StreamReset stream_id:1, error_code:2>`). BBL's edge does JA3 / TLS
  fingerprint matching on direct clients. Playwright's Chromium bundle
  presents a real Chrome TLS handshake and passes. No anti-bot challenge
  beyond the TLS gate — no Cloudflare, no Akamai, no JS challenge.
- **PROMOTION_URL:** `/en/Personal/Cards/Credit-Cards/Promotions` (EN hub).
  The TH equivalent (`/th/Personal/Cards/Credit-Cards/Promotions`) and the
  Thai landing (`/th`) itself both return HTTP 500 — BBL's Thai Sitecore
  instance is intermittently broken as of 2026-04-22. EN and TH render the
  same Sitecore component with identical DOM, so swapping the URL back when
  BBL repairs it is a one-line change; selectors carry over.
- **Selectors:** `.thumb-default` wraps each card. Inside:
  - `.thumb[style*=background-image]` → thumbnail URL (BBL uses CSS
    background-image, not plain `<img>`, with a hidden `img.img-print`
    mirror for print-stylesheet rendering). Parser extracts the URL via
    regex on the `style` attribute and falls back to the print `img` tag.
  - `.caption .desc` → title/description (BBL doesn't ship a separate
    description field in the tile; we duplicate the title).
  - `.promotion-tip` → category ("Newsletter", "Dining", "Shopping", etc.)
  - `.promotion-valid` → date range (see below)
  - `a.btn-primary` → CTA link to detail page
- **Dates:** `_parse_date_range` accepts both:
  - EN: `"1 Mar 2026 until 30 Apr 2026"` (current production format)
  - TH: `"1 มี.ค. 2569 ถึง 30 เม.ย. 2569"` (future-proofing for when BBL
    fixes the TH locale). BE → CE conversion handled by the shared Thai
    date helper.
- **Merchant extraction:** Thai preposition (`ที่`, `ร่วมกับ`) plus an
  English `"at X"` pattern for EN-locale copy. Blocklist suppresses BBL
  brand variants and both Thai (มกราคม–ธันวาคม) and English (January–
  December) month names.
- **URL handling:** `urljoin(PROMOTION_URL, href)` resolves relative
  `/en/Personal/...` links against the hub. `source_id` is the last path
  segment with any `?utm_*` query stripped.

## Tests

- `tests/adapters/test_bbl_parser.py` — 9 tests, all green:
  - mixed-fixture smoke test parses all 3 cards (1 live + 2 synthetic)
  - background-image URL extraction from the `style` attribute
  - empty HTML → `[]`
  - EN "until" date range + Thai BE "ถึง" date range
  - Thai `ที่` and English `at` merchant patterns
  - blocklist suppresses "Bangkok Bank" and stray English month names
  - relative hrefs resolve to absolute URLs

## Anti-bot observations

- TLS fingerprint gate (any non-Chrome-like handshake gets stream-reset).
- `robots.txt` does not disallow `/en/Personal/Cards/Credit-Cards/Promotions`.
- Rate limit: 5 s between requests.
- No Cloudflare / Akamai / hCaptcha observed.

## Expected row count

- 1 card visible on 2026-04-22. BBL's EN hub has a category carousel with
  11 `.liCategoryMobile` tabs (data-category-id Sitecore GUIDs), but
  clicking them fires an AJAX filter call — tabs don't pre-render. The 1
  visible tile is what appears in the default "All" view.
- When BBL recovers its Thai locale / refreshes the promo catalog, the same
  parser should scale to 40–70 cards without changes.

## Follow-ups (not blockers)

1. **Monitor the TH locale.** When `/th/Personal/Cards/Credit-Cards/Promotions`
   starts returning 200, flip `PROMOTION_URL` in `constants.py`. The test
   fixture already covers Thai BE date parsing.
2. **Walk the category tabs.** The `.liCategoryMobile` tabs carry
   `data-category-id` GUIDs that feed a Sitecore API; capture the XHR
   endpoint and either hit it directly or click each tab in sequence via
   Playwright. Potentially adds 20–40 more tiles.
3. **Re-capture the live fixture** once BBL surfaces more than one tile,
   and drop the synthetic cards. Track this as a cleanup PR.
4. **Alert on < 3 promos** from a scrape run — BBL's thin catalog makes
   "adapter broken" look identical to "BBL has 1 promo today". A soft
   lower bound in the pipeline sanity check would distinguish the two.
