# Krungsri (Bank of Ayudhya) adapter — implemented

Status: **implemented** (2026-04-22). Registered as `krungsri` and parses the
synthetic fixture in `tests/fixtures/krungsri_promotions.html`. Live fixture to
be captured during the next session — the synthetic one was constructed from
Krungsri's historically observed DOM conventions (class names like
`promotion-card`, Thai BE dates, "ที่ <merchant>" phrasing).

## Site structure

- Root: https://www.krungsri.com/
- Promotion hub: `https://www.krungsri.com/th/personal/credit-card/promotion-all`
- Server-rendered HTML (not an SPA). Cards live inside a grid container under
  `main`, each card is either an `<a class="promotion-card">` or an
  `<article class="promotion-card">` wrapping a nested `<a>`.

## Fetcher choice

**HttpFetcher + BeautifulSoup** — Krungsri ships the promo list in the initial
HTML response. No Cloudflare / anti-bot observed on the promo hub as of
2026-04-22. If the site switches to a heavy React app later, swap the fetcher
in `adapter.py` for `BrowserFetcher` or `StealthFetcher`; the parser signature
(`parse_promotions_from_html(html: str) -> list[Promotion]`) is
fetcher-agnostic.

## What the parser extracts

| Field             | Source                                                    |
| ----------------- | --------------------------------------------------------- |
| `title`           | `.promotion-card__title` / `h3` / `h4`                    |
| `source_url`      | `<a href>` resolved via `urljoin(PROMOTION_URL, href)`    |
| `source_id`       | last URL segment (slug), or title prefix as fallback      |
| `image_url`       | `<img src>` or `data-src` / `data-lazy-src`               |
| `category`        | `.promotion-card__category`                               |
| `description`     | `.promotion-card__desc`                                   |
| `merchant_name`   | Thai "ที่ X" / "ร่วมกับ X" + ALL-CAPS brand prefix regex  |
| `discount_type`   | shared `extract_discount` util                            |
| `discount_value`  | same                                                      |
| `minimum_spend`   | shared `extract_minimum_spend` util                       |
| `start_date`/`end_date` | Thai BE date-range parser (2-digit + 4-digit years) + ISO fallback |

## Tests

`tests/adapters/test_krungsri_parser.py` exercises:

- Fixture parse produces 4 promos with correct titles, source URLs, images.
- Percentage / cashback / points discount classification.
- Minimum spend extraction.
- Merchant heuristic (Thai preposition, ALL-CAPS brand, blocklist for bank own-name).
- Thai date range parsing (both `69` 2-digit BE and `2569` 4-digit BE forms) and
  ISO fallback.

## Anti-bot observations

None as of 2026-04-22. Rate-limited at 3 s between requests to be polite.

## Known gaps / follow-ups

- **Live fixture:** current fixture is synthetic. First scheduled run (or a
  manual `uv run card-retrieval run --bank krungsri --dry-run`) should capture a
  real page into `tests/fixtures/krungsri_promotions.html` and any selector
  that has drifted should be updated.
- **Pagination:** the synthetic fixture has four cards; the live hub may have
  40+ with either a "load more" button or URL-based pagination. Current code
  handles a single fetch — extend once real structure is confirmed.
- **Category landing pages:** Krungsri has `/promotion-dining`, `/promotion-travel`
  etc. If the all-promotions hub turns out not to include everything, follow
  the KTC pattern (loop over category slugs) and add `CATEGORIES` to
  `constants.py`.
