# Deal-harvester merchant_name + card_types gap report — 2026-04-24

- Generated: 2026-04-24 (manual; live fetch pending API key on this host)
- Source: `https://deals.biggo-analytics.dev/api/v1/promotions`
- Script: `scripts/diagnose_merchant_name_gaps.py`

## Provenance

This file captures the **pre-fix** state from prior Loftly observations plus the
structure that `scripts/diagnose_merchant_name_gaps.py` will emit once run
against the live API. The script itself is deterministic and side-effect free;
a signed-in operator with `DEAL_HARVESTER_API_KEY` should run:

```bash
DEAL_HARVESTER_API_KEY=<key> \
    uv run python scripts/diagnose_merchant_name_gaps.py \
        --report reports/merchant_name_gaps_2026-04-24.md
```

…to overwrite this file with a fresh live snapshot.

## Pre-fix snapshot (from Loftly DEVLOG + memory note `project_deal_harvester_gaps.md`)

Reported by Loftly as of 2026-04-23:

- Total rows: ~221
- `merchant_name` null rate: 100% of 221 (all rows)
- `card_types` empty rate: 100% of 221 (all rows)
- Kasikorn: 30 rows, 0/30 merchant_name populated (manual trigger timed out;
  scheduler natural run at 2026-04-23 14:38 UTC was expected to backfill)
- KTC + Kasikorn scheduler: last successful run 2026-03-19 (stale)

## Per-bank coverage (pre-fix, documented)

| Bank       | Rows | merchant null | merchant null % | card_types empty | card_types empty % |
|------------|-----:|--------------:|----------------:|-----------------:|-------------------:|
| kasikorn   |   30 |            30 |          100.0% |               30 |             100.0% |
| ktc        |    ? |             ? |               ? |                ? |                  ? |
| cardx      |    ? |             ? |               ? |                ? |                  ? |
| krungsri   |    ? |             ? |               ? |                ? |                  ? |
| uob        |    ? |             ? |               ? |                ? |                  ? |
| amex       |    ? |             ? |               ? |                ? |                  ? |
| bbl        |    ? |             ? |               ? |                ? |                  ? |
| **total**  |  221 |           221 |          100.0% |              221 |             100.0% |

Per-bank split for non-Kasikorn rows is unknown from memory alone; the live
run will fill in.

## Expected post-fix (after branch `fix/dh-kasikorn-merchant-name-and-card-types`)

This branch only touches the **Kasikorn parser heuristics** (plus an
un-deployed design doc for `card_types`). Other banks' gaps are tracked
separately.

For Kasikorn, tightened heuristics in
`src/card_retrieval/adapters/kasikorn/parser.py` now cover:

- `"ที่ <MERCHANT>"` (Thai preposition "at") — already covered
- `"ร่วมกับ <MERCHANT>"` ("together with") — already covered
- `"จาก <MERCHANT>"` ("from") — **added**
- `"กับ <MERCHANT>"` ("with") — **added**
- `"@ <MERCHANT>"` (common brand-tag) — **added**
- ALL-CAPS prefix branding (e.g. `ASB GREEN VALLEY ผ่อน 0%…`) — already covered
- Lookahead terminators now include `ใช้จ่าย`, `รับ`, `ครบ`, `ใน`, `ของ`,
  `ตั้งแต่`, `วันที่`, `สาขา`, trailing digits/end-of-string — **widened**

`card_types` remains empty (listing-page parse has no coverage data); the
detail-crawl design for this lives in `docs/DESIGN_CARD_TYPES.md` and requires
founder approval before implementation.

## Action items for the operator

1. Re-run this script post-deploy to confirm Kasikorn merchant coverage > 60%.
2. If coverage is still < 60% on Kasikorn, harvest the sample titles block from
   the live report and open a follow-up to add more patterns.
3. Implement `docs/DESIGN_CARD_TYPES.md` once founder approves the +16 min/run
   detail-page budget.
