from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Simple per-domain rate limiter."""

    def __init__(self):
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str, interval: float):
        async with self._lock:
            last = self._last_request.get(domain, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request[domain] = time.monotonic()


rate_limiter = RateLimiter()
