import pytest

from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.models import Promotion
from card_retrieval.core.registry import _registry, get_adapter, list_adapters, register


class _DummyAdapter(BaseAdapter):
    def get_bank_name(self) -> str:
        return "dummy"

    def get_source_url(self) -> str:
        return "https://dummy.com"

    async def fetch_promotions(self) -> list[Promotion]:
        return []


def test_register_and_get():
    register("test_dummy")(_DummyAdapter)
    cls = get_adapter("test_dummy")
    assert cls is _DummyAdapter
    # Cleanup
    _registry.pop("test_dummy", None)


def test_get_unknown_adapter():
    with pytest.raises(KeyError, match="Unknown adapter"):
        get_adapter("nonexistent_bank_xyz")


def test_list_adapters_includes_registered():
    register("test_list")(_DummyAdapter)
    adapters = list_adapters()
    assert "test_list" in adapters
    _registry.pop("test_list", None)
