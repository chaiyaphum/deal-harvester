#!/usr/bin/env python3
"""Diagnose merchant_name (and card_types) coverage gaps across banks.

Hits the live deal-harvester API and buckets promotions by bank, reporting the
per-bank null-rate for ``merchant_name`` and empty-rate for ``card_types``.
Also samples up to ``--title-samples`` raw titles per bank for banks whose
coverage is < 80%, so a human can eyeball the title corpus and tighten the
parser heuristics.

Usage::

    DEAL_HARVESTER_API_KEY=<key> uv run python scripts/diagnose_merchant_name_gaps.py \
        --base https://deals.biggo-analytics.dev/api/v1 \
        --report reports/merchant_name_gaps_$(date +%F).md

Notes
-----
* Safe to run repeatedly — read-only. No ``/scrape/trigger`` calls.
* Paginates at ``page_size=100`` (API max) and stops at the last page.
* When ``--report`` is given, writes a Markdown summary; stdout always gets
  the same table. Exit code is 0 on success, 2 on transport/auth errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE = "https://deals.biggo-analytics.dev/api/v1"
PAGE_SIZE = 100
# Single-page timeout. Kasikorn's Xvfb pipeline is slow but the READ path is cheap.
HTTP_TIMEOUT_SECONDS = 30


def _fetch_page(base: str, api_key: str, page: int, *, is_active: bool | None) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "page_size": PAGE_SIZE}
    if is_active is not None:
        params["is_active"] = str(is_active).lower()
    url = f"{base.rstrip('/')}/promotions?{urlencode(params)}"
    req = Request(url, headers={"X-API-Key": api_key, "Accept": "application/json"})
    with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(base: str, api_key: str, *, is_active: bool | None) -> list[dict[str, Any]]:
    """Fetch every promotion across all pages."""
    first = _fetch_page(base, api_key, 1, is_active=is_active)
    items: list[dict[str, Any]] = list(first.get("items", []))
    total = int(first.get("total", len(items)))
    pages = int(first.get("pages", 1))
    for p in range(2, pages + 1):
        chunk = _fetch_page(base, api_key, p, is_active=is_active)
        items.extend(chunk.get("items", []))
    # Sanity check: the API may have advanced underneath us; don't fail hard.
    if len(items) != total:
        print(
            f"[warn] fetched {len(items)} items but API reported total={total}",
            file=sys.stderr,
        )
    return items


def _is_empty_card_types(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def bucket_by_bank(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return per-bank stats + per-bank sample titles."""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "merchant_null": 0,
            "card_types_empty": 0,
            "sample_titles_missing_merchant": [],
        }
    )
    for item in items:
        bank = item.get("bank") or "unknown"
        b = buckets[bank]
        b["total"] += 1
        if not item.get("merchant_name"):
            b["merchant_null"] += 1
            if len(b["sample_titles_missing_merchant"]) < 10:
                title = (item.get("title") or "").strip()
                if title:
                    b["sample_titles_missing_merchant"].append(title)
        if _is_empty_card_types(item.get("card_types")):
            b["card_types_empty"] += 1
    return dict(buckets)


def _fmt_pct(n: int, d: int) -> str:
    if d == 0:
        return "—"
    return f"{(100 * n / d):.1f}%"


def render_report(
    buckets: dict[str, dict[str, Any]],
    *,
    base: str,
    is_active: bool | None,
    title_samples: int,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total = sum(b["total"] for b in buckets.values())
    merchant_null = sum(b["merchant_null"] for b in buckets.values())
    ct_empty = sum(b["card_types_empty"] for b in buckets.values())

    lines: list[str] = []
    lines.append("# Deal-harvester merchant_name + card_types gap report")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Source: `{base}/promotions` (is_active={is_active})")
    lines.append(f"- Total rows: {total}")
    lines.append(f"- merchant_name null: {merchant_null} ({_fmt_pct(merchant_null, total)})")
    lines.append(f"- card_types empty: {ct_empty} ({_fmt_pct(ct_empty, total)})")
    lines.append("")
    lines.append("## Per-bank coverage")
    lines.append("")
    lines.append(
        "| Bank | Rows | merchant null | merchant null % | card_types empty | card_types empty % |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for bank in sorted(buckets.keys()):
        b = buckets[bank]
        lines.append(
            f"| {bank} | {b['total']} | {b['merchant_null']} | "
            f"{_fmt_pct(b['merchant_null'], b['total'])} | "
            f"{b['card_types_empty']} | "
            f"{_fmt_pct(b['card_types_empty'], b['total'])} |"
        )
    lines.append("")

    # Per-bank samples — only emit for banks that are < 80% covered on merchant_name
    bad_banks = [
        (bank, b)
        for bank, b in buckets.items()
        if b["total"] > 0 and b["merchant_null"] / b["total"] > 0.2
    ]
    if bad_banks:
        lines.append("## Sample titles with merchant_name=null")
        lines.append("")
        lines.append(
            "Banks below 80% merchant coverage; up to "
            f"{title_samples} titles per bank for heuristic tuning."
        )
        lines.append("")
        for bank, b in sorted(bad_banks):
            lines.append(f"### {bank}")
            lines.append("")
            for t in b["sample_titles_missing_merchant"][:title_samples]:
                lines.append(f"- {t}")
            lines.append("")

    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base", default=os.environ.get("DEAL_HARVESTER_BASE", DEFAULT_BASE))
    p.add_argument(
        "--api-key",
        default=os.environ.get("DEAL_HARVESTER_API_KEY", ""),
        help="API key (or set DEAL_HARVESTER_API_KEY env)",
    )
    p.add_argument(
        "--is-active",
        choices=("true", "false", "all"),
        default="all",
        help="Filter by is_active; 'all' disables the filter (default).",
    )
    p.add_argument(
        "--report",
        default=None,
        help="Optional path to write Markdown report; stdout always gets the summary.",
    )
    p.add_argument("--title-samples", type=int, default=10)
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.api_key:
        print(
            "error: DEAL_HARVESTER_API_KEY not set (use env var or --api-key).",
            file=sys.stderr,
        )
        return 2

    is_active: bool | None
    is_active = None if args.is_active == "all" else (args.is_active == "true")

    try:
        items = fetch_all(args.base, args.api_key, is_active=is_active)
    except HTTPError as e:  # noqa: BLE001
        print(f"error: HTTP {e.code} from {args.base}: {e.reason}", file=sys.stderr)
        return 2
    except URLError as e:  # noqa: BLE001
        print(f"error: transport failure: {e.reason}", file=sys.stderr)
        return 2

    buckets = bucket_by_bank(items)
    report = render_report(
        buckets,
        base=args.base,
        is_active=is_active,
        title_samples=args.title_samples,
    )
    sys.stdout.write(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"[ok] report written → {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
