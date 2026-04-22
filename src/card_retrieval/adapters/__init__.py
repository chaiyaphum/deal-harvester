"""Import all adapters to trigger registration."""

from card_retrieval.adapters.amex import adapter as _amex  # noqa: F401
from card_retrieval.adapters.bbl import adapter as _bbl  # noqa: F401
from card_retrieval.adapters.cardx import adapter as _cardx  # noqa: F401
from card_retrieval.adapters.kasikorn import adapter as _kasikorn  # noqa: F401
from card_retrieval.adapters.krungsri import adapter as _krungsri  # noqa: F401
from card_retrieval.adapters.ktc import adapter as _ktc  # noqa: F401
from card_retrieval.adapters.uob import adapter as _uob  # noqa: F401
