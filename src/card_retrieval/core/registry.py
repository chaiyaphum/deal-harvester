from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from card_retrieval.core.base_adapter import BaseAdapter

_registry: dict[str, type[BaseAdapter]] = {}


def register(name: str):
    """Decorator to register an adapter class."""

    def decorator(cls: type[BaseAdapter]) -> type[BaseAdapter]:
        _registry[name] = cls
        return cls

    return decorator


def get_adapter(name: str) -> type[BaseAdapter]:
    if name not in _registry:
        available = ", ".join(_registry.keys()) or "(none)"
        raise KeyError(f"Unknown adapter '{name}'. Available: {available}")
    return _registry[name]


def list_adapters() -> dict[str, type[BaseAdapter]]:
    return dict(_registry)
