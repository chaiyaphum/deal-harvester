from __future__ import annotations

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from card_retrieval.core.exceptions import FetchError

logger = structlog.get_logger()

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
}


class HttpFetcher:
    def __init__(self, headers: dict[str, str] | None = None, timeout: float = 30.0):
        self._headers = {**DEFAULT_HEADERS, **(headers or {})}
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=self._timeout,
                http2=True,
                follow_redirects=True,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch(self, url: str) -> str:
        client = await self._get_client()
        log = logger.bind(url=url)
        log.debug("http_fetch_start")
        try:
            response = await client.get(url)
            response.raise_for_status()
            log.debug("http_fetch_ok", status=response.status_code, size=len(response.text))
            return response.text
        except httpx.HTTPError as e:
            log.error("http_fetch_error", error=str(e))
            raise FetchError(f"Failed to fetch {url}: {e}") from e

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
