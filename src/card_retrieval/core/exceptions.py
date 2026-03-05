class CardRetrievalError(Exception):
    """Base exception for card retrieval system."""


class FetchError(CardRetrievalError):
    """Error during data fetching."""


class ParseError(CardRetrievalError):
    """Error during data parsing."""


class AdapterError(CardRetrievalError):
    """Error in a bank adapter."""


class StorageError(CardRetrievalError):
    """Error during data storage."""
