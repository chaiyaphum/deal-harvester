# Krungsri (Bank of Ayudhya) adapter — implemented (live fixture)

Status: **implemented, live fixture** (2026-04-22). Registered as `krungsri`
and parses a trimmed live capture in `tests/fixtures/krungsri_promotions.html`
(11 tiles across 4 category hubs). Earlier session shipped against a synthetic
fixture — that has now been replaced with real DOM.

## Site structure (live)

- Root: https://www.krungsri.com/
- Promotion landing: `https://www.krungsri.com/th/promotions/cards`
- Category sub-pages: `/th/promotions/cards/{slug}` where slug ∈
  {hot-promotion, dining, shopping-online, travel, ...}
- The historical `/th/personal/credit-card/promotion-all` path in our earlier
  plan is a hard 404 behind Incapsula. Caught during live capture.
- Each category hub is server-rendered (no client-side pagination for tile
  contents) and exposes 1–6 tiles. Hot-promotion is the largest (6);
  dining/shopping/travel each serve 1–2. Walking all four yields ~11 tiles.
- Tile shape: `<div class="card-info item">` wrapping `<a href="…">` →
  `<div class="image"><picture>…<img src="/getmedia/…webp"></picture></div>`
  and `<div class="content"><div class="header"><h3>title</h3></div><p>desc</p></div>`.
- No inline date or category slot on listing pages — both live on detail
  pages. Parser gracefully surfaces `None` for both; adapter stamps
  category based on the hub slug.

## Fetcher choice

**StealthFetcher + pre-visit to `/th/`** — required.

- Plain `httpx` / `curl` → HTTP 200 with a 958-byte Incapsula challenge
  iframe (`/_Incapsula_Resource?SWJIYLWA=…`). Zero tiles parseable.
- `StealthFetcher` with pre-visit to `/th/` → the warm-up sets the
  Incapsula cookies, the subsequent navigation to
  `/th/promotions/cards/{slug}` returns ~540–590 KB of rendered HTML with
  all `div.card-info` tiles present.
- We warm the context once per adapter run and reuse the same Playwright
  browser session across all 4 hub fetches. `rate_limiter.wait(…, 3.0 s)`
  between hubs keeps us polite.

## What the parser extracts

| Field             | Source                                                     |
| ----------------- | ---------------------------------------------------------- |
| `title`           | `.card-info .header h3` (fallback: bare `h3`)              |
| `source_url`      | `<a href>` (absolute on Krungsri — no `urljoin` needed)    |
| `source_id`       | last URL segment (slug)                                    |
| `image_url`       | `<img src>` — `/getmedia/…webp` resolved against BASE_URL  |
| `category`        | Stamped by adapter from hub slug (not on listing DOM)      |
| `description`     | `.card-info .content > p`                                  |
| `merchant_name`   | Thai "ที่ X" / "ร่วมกับ X" heuristic + ALL-CAPS brand prefix |
| `discount_type`   | shared `extract_discount` util                             |
| `discount_value`  | same                                                       |
| `minimum_spend`   | shared `extract_minimum_spend` util                        |
| `start_date`/`end_date` | `None` for listing-sourced tiles (detail pages only) |

## Tests

`tests/adapters/test_krungsri_parser.py` exercises the live fixture:

- Fixture parses to 11 promos spanning hot-promotion + dining + shopping-online + travel.
- `Hotels.com` / `Expedia` / `dining-discount` / `discount-with-avis` /
  `rakuten-travel` produce percentage discounts (`7%`, `7%`, `20%`, `20%`, `8%`).
- `fifa-world-cup-2026` (no numeric discount in title/desc) correctly
  returns `None` for discount fields.
- Listing tiles surface `None` for both `start_date` and `category` — the
  adapter stamps category from the hub slug after parsing.
- Merchant heuristic and Thai-date range parsing still pass against
  synthetic inputs (`Centara Grand Buffet`, Buddhist-era 2-digit and
  4-digit years, ISO fallback).

## Anti-bot observations

Incapsula/Imperva is active. Without the pre-visit warm-up, every request
returns a challenge page. `StealthFetcher` already injects the standard
anti-webdriver script + launches with
`--disable-blink-features=AutomationControlled`; that plus the pre-visit
was sufficient on 2026-04-22. If Krungsri tightens, the next escalation is
randomized viewport/UA per session (already present in StealthFetcher) or
a longer human-like delay after the pre-visit.

## Known gaps / follow-ups

- **Detail-page enrichment:** to get actual date ranges / `category` /
  richer descriptions we need to follow each `source_url` to the detail
  page. Deferred — keeping the adapter listing-only for now is consistent
  with the other bank adapters.
- **Fixture size:** 10 KB (11 tiles). Lower than the 30–80 KB guideline
  the task suggested — reflects the real site surface. Krungsri ships a
  lean listing. If we enrich with detail pages later, per-promo HTML will
  push the fixture into the 50–100 KB range.
- **Additional categories:** the live nav also exposes categories beyond
  the 4 we walk (e.g., `/entertainment`, `/health`, `/petrol`). If we
  later discover any of them carry tiles, append to `CATEGORY_SLUGS` in
  `constants.py`.
