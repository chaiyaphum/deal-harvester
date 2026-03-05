"""Import all adapters to trigger registration."""

from card_retrieval.adapters.ktc import adapter as _ktc  # noqa: F401
from card_retrieval.adapters.cardx import adapter as _cardx  # noqa: F401
from card_retrieval.adapters.kasikorn import adapter as _kasikorn  # noqa: F401
