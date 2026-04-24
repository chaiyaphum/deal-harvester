# Design: detail-page crawl for per-promo `card_types`

Status: **design only — not implemented.** Requires founder approval before
implementation because the runtime budget grows materially (see §3).

Owners: deal-harvester maintainer. Loftly consumes via
`DEAL_HARVESTER_BASE`.

Related:

- `Promotion.card_types` (`src/card_retrieval/core/models.py`) — currently
  `[]` on every row across all 7 bank adapters.
- `Promotion.checksum` widened 2026-04-22 in commit `05d1281` — now includes
  `card_types` in the hash, so a re-crawl that populates the field will
  correctly trigger upserts on existing rows.

---

## 1. Problem

Every promo today has `card_types=[]`. Loftly's selector ranking wants to
resolve promos to specific cards so it can surface only the promos the user
actually holds (see Loftly `mvp/SPEC.md` — promo context block).

Bank listing pages don't publish card coverage per tile. The per-promo
detail page (linked via the tile's CTA `<a href>`) does: KBank in particular
renders a `"บัตรที่ร่วมรายการ"` ("participating cards") block with card
names, and BBL/KTC/CardX/UOB/Amex/Krungsri all have equivalent sections
under various headings.

## 2. Proposed approach

### 2.1 Shape

Add an **optional second fetch** inside each adapter, gated by a per-adapter
`ENABLE_DETAIL_CRAWL: bool` constant (default `False`):

```
fetch_promotions()
├── fetch_listing()       → N tiles with title + source_url
└── for each tile:
    └── if ENABLE_DETAIL_CRAWL:
        fetch_detail(tile.source_url) → card_types: list[str]
```

Detail-page parsing lives in a new `parser_detail.py` per adapter, keyed on
bank-specific selectors (a single shared parser won't work — each bank's
detail page is structurally different).

### 2.2 Rate-limit math

Rate limits per bank (from `constants.py`):

| Bank      | `RATE_LIMIT_SECONDS` | Tiles (today) | Detail pages | Add'l time per run |
|-----------|---------------------:|--------------:|-------------:|-------------------:|
| kasikorn  |                  10 |            30 |           30 |       **+300s (5m)** |
| ktc       |                   2 |           ~50 |          ~50 |             **+100s** |
| cardx     |                   5 |           ~20 |          ~20 |             **+100s** |
| krungsri  |                   3 |           ~40 |          ~40 |             **+120s** |
| uob       |                   4 |           ~30 |          ~30 |             **+120s** |
| amex      |                   6 |           ~30 |          ~30 |             **+180s** |
| bbl       |                   5 |             1 |            1 |               **+5s** |

> **Kasikorn is the bottleneck.** 30 detail fetches × 10s rate limit = 5
> minutes additional wall time per run. Adding realistic page render + DOM
> settle (~20s each on Xvfb stealth), the Kasikorn run budget grows
> **~+16 minutes** (30 × 32s ≈ 960s).

Total across all 7 banks: roughly **+23 minutes per full scheduler cycle**.
Today each scheduler cycle runs every 6 hours, so 4×/day × 23min = +92min
compute/day. Acceptable for a 2-core container, but **not** while we're
still dialing in stealth stability.

### 2.3 Incremental vs full-rescan policy

**Full rescan is wasteful.** The detail page changes roughly as often as
the listing tile — ~monthly. Proposed policy:

- **Hot path (scheduler run):** listing-only. Detail crawl runs only for
  rows whose `source_url` is **new** in the current run (i.e. not present in
  the previous run's result set).
- **Cold path (weekly batch):** re-crawl detail for every active row
  (`is_active=true AND end_date >= today`) to catch silent edits.
  Scheduled as a separate cron, off-peak (04:00 ICT / 21:00 UTC).

Heuristic estimate for hot-path load: typically 2-5 new promos per bank per
day — so ~+30s Kasikorn hot-path, not +16min. The weekly rescan eats the
full +16min once per week per bank.

### 2.4 Checksum implications

Commit `05d1281` (2026-04-22) widened `Promotion.checksum` to include
`card_types` in the hash:

```python
# src/card_retrieval/core/models.py, L44
"card_types": sorted(self.card_types) if self.card_types else [],
```

Consequences:

1. When detail-crawl ships and starts populating `card_types`, **every
   existing row's checksum changes** on its first re-crawl. The repository
   layer's upsert-by-checksum will mark all 221 current rows as "updated"
   — intentional, because they genuinely have new data, but worth calling
   out in the deploy PR so the operator isn't surprised by a spike in
   `promotions_updated` on the first post-deploy run.
2. `sorted(self.card_types)` ensures stable checksum regardless of detail
   DOM ordering — so a future re-parse that happens to surface cards in a
   different order won't cause a spurious update.
3. Loftly's `promo_snapshot` service invalidates its cache on
   `deal-harvester` sync via the checksum digest (see Loftly
   `mvp/AI_PROMPTS.md` — "digest included in cache key so a new sync
   invalidates the block cleanly"). The mass-upsert will cause a single
   cache bust on first deploy; no further work needed.

### 2.5 Timeline estimate

Assuming founder approval, order-of-magnitude:

| Milestone                                      | Effort   |
|------------------------------------------------|----------|
| Shared `BaseDetailParser` + extraction helpers | 0.5 day  |
| Per-bank detail parsers (7 × ~half day)        | 3.5 days |
| Wire `ENABLE_DETAIL_CRAWL` config + tests      | 0.5 day  |
| Weekly rescan cron job                         | 0.5 day  |
| Deploy, monitor one full rescan, patch gaps    | 1.0 day  |
| **Total**                                      | **~6 days** |

## 3. Approval gate

**Do not merge detail-crawl code without founder sign-off on:**

- The +16 min Kasikorn scheduler run budget (nor the +92 min/day total).
- The mass-upsert on first post-deploy run (cosmetic alarm risk).
- The weekly rescan cron addition to the compose stack.

## 4. Out of scope

- Parsing per-card *eligibility rules* (min spend varies by card) — that's
  a richer detail model and would need a schema change. For MVP, `card_types`
  is a flat list of card-name strings; Loftly's canonicalizer maps them to
  Loftly card IDs.
- Card-tier detection (Signature vs Infinite). KBank sometimes lists
  "บัตรเครดิตกสิกรไทย ทุกประเภท" ("all types"); treat this as a wildcard
  and leave Loftly's canonicalizer to expand.
- Image-based card logos (some banks show logos without card-name text).
  Would need OCR; deferred.
