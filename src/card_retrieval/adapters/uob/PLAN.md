# UOB Thailand adapter — implementation plan

Status: **implemented** (2026-04-22). `fetch_promotions` returns a deduplicated
list of `Promotion` objects parsed from the live hub. Live-captured HTML
fixture ships in `tests/fixtures/uob_promotions.html` (9 cards, trimmed from
~317 KB to ~15 KB).

## What actually shipped

- **Fetcher:** `HttpFetcher` with the default Chrome UA and `Accept-Language:
  th-TH`. UOB publishes the hub at
  `/personal/promotions/creditcard/all-promotion.page` (sourced from
  `credit-cards-th-sitemap.xml`). The response is a 301 → the canonical hub at
  `/personal/credit-cards/promotions.page`; httpx follows transparently and we
  get the fully populated AEM-rendered HTML in one round trip. No Cloudflare /
  Akamai challenge observed; no JS rendering required.
- **Card selector:** `.category-item` (9 curated tiles). Each tile contains
  `img.card-img-top`, `h4.card-title`, `p.paragraph`, and a CTA anchor
  `a.dtm-button`. See `constants.SELECTORS` — selectors are intentionally loose
  (fallback to `h4`, `img`, `p`) so small class reshuffles do not break
  parsing.
- **Merchant extraction:** reuses the Krungsri/Kasikorn Thai-preposition
  heuristic (`ที่ X`, `ร่วมกับ X`). UOB descriptions often contain date phrases
  like "ที่ 18 มีนาคม 2568" — the merchant blocklist was expanded to include
  Thai month names (มกราคม … ธันวาคม) to suppress these false positives. Most
  UOB hub promos are cross-category (concert tickets, refinance campaigns) and
  don't include a discrete merchant, so `merchant_name` is `None` for the
  majority; that is correct, not a bug.
- **URL handling:** `urljoin(PROMOTION_URL, href)` so relative, absolute, and
  cross-domain (`go.uob.com`, `/revamp/personal/redirect/...`) links all
  resolve. `source_id` strips `?utm_*` query strings so marketing-tag churn
  doesn't invalidate promo checksums between scrapes.
- **Dates:** UOB listing cards don't expose a structured date field; dates
  live on the per-promo detail page. The parser makes a best-effort Thai/ISO
  range match on the description and returns `None/None` when nothing is found
  (same bar as Krungsri).

## Anti-bot observations

- No Cloudflare challenge on the promotions hub as of 2026-04-22.
- `robots.txt` explicitly disallows `/cgi-bin/`, `/th/pdf/`, `/templatedata/`
  but not the promotions path.
- Rate limit: 4.0 s between requests (conservative; hub responds in ~2 s).

## Expected row count

- 9 curated tiles on the hub. UOB surfaces highlight promos only; per-category
  pages (`/dining.page`, `/highlight.page`) are marketing landing pages, not
  card lists. If we later want 30–60 rows, the move is to follow each tile's
  CTA to the detail page and also walk the carousel slider (`.tile-card-slide`)
  — out of scope for the MVP single-page scrape.

## Tests

- `tests/adapters/test_uob_parser.py` — 9 tests, all green:
  - parses 9 cards out of the live fixture
  - all URLs are absolute; images resolved against `BASE_URL`
  - `source_id` strips `utm_*` query params (regression protection for
    dedupe/checksum churn)
  - `/revamp/` redirect paths survive intact
  - relative `/personal/...` hrefs resolve via `urljoin`
  - empty HTML → `[]`
  - Thai-preposition merchant extraction works for `ที่ Starbucks`
  - Thai month-name blocklist suppresses "ที่ 18 มีนาคม" false positives
  - UOB brand names blocked from merchant slot
  - Western `01/04/2026 – 30/09/2026` and Thai BE ranges both parse

## Follow-ups (not blockers)

1. Walk the `.tile-card-slide` carousel on the hub — may surface an additional
   ~20 promos that rotate in/out.
2. Fetch per-promo detail pages to enrich `start_date`, `end_date`, and
   `terms_and_conditions`. Requires a second fetch round per card, so
   probably gate behind a config flag.
3. Re-capture the fixture on the first post-Songkran site refresh (UOB tends
   to re-skin AEM templates seasonally).
