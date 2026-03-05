from __future__ import annotations

import abc

from card_retrieval.core.models import Promotion


class BaseAdapter(abc.ABC):
    @abc.abstractmethod
    def get_bank_name(self) -> str: ...

    @abc.abstractmethod
    def get_source_url(self) -> str: ...

    @abc.abstractmethod
    async def fetch_promotions(self) -> list[Promotion]: ...

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
