from __future__ import annotations

from card_retrieval.core.models import Promotion


def parse_promotions_from_html(html: str) -> list[Promotion]:
    """Stub. See adapters/amex/PLAN.md for the implementation plan."""
    raise NotImplementedError(
        "Amex TH parser is not implemented yet — see adapters/amex/PLAN.md"
    )
