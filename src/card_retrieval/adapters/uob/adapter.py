from __future__ import annotations

import structlog

from card_retrieval.adapters.uob.constants import BANK_NAME, PROMOTION_URL
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import register

logger = structlog.get_logger()


@register("uob")
class UobAdapter(BaseAdapter):
    """UOB Thailand credit-card promotion adapter — SCAFFOLD ONLY.

    Registered so `list-adapters` surfaces the target, but `fetch_promotions`
    raises NotImplementedError until the parser is built. See PLAN.md for the
    site-structure notes, fetcher rationale, and estimated effort.
    """

    def get_bank_name(self) -> str:
        return BANK_NAME

    def get_source_url(self) -> str:
        return PROMOTION_URL

    async def fetch_promotions(self) -> list[Promotion]:
        raise NotImplementedError(
            "UOB adapter is a scaffold — see src/card_retrieval/adapters/uob/PLAN.md"
        )
