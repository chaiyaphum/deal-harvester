from __future__ import annotations

import asyncio

import structlog
from playwright.async_api import Browser, Page, Playwright, async_playwright

from card_retrieval.config import settings
from card_retrieval.core.exceptions import FetchError

logger = structlog.get_logger()


class BrowserFetcher:
    """Playwright-based fetcher for JS-rendered sites."""

    def __init__(self, headless: bool | None = None):
        self._headless = headless if headless is not None else settings.browser_headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self._headless)
        return self._browser

    async def new_page(self) -> Page:
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
        )
        return await context.new_page()

    async def fetch_with_intercept(
        self,
        url: str,
        intercept_pattern: str,
        wait_time: float = 5.0,
    ) -> list[dict]:
        """Navigate to URL and capture API responses matching the pattern."""
        page = await self.new_page()
        captured: list[dict] = []

        async def handle_response(response):
            if intercept_pattern in response.url:
                try:
                    data = await response.json()
                    captured.append(data)
                    logger.debug("intercepted_response", url=response.url)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout)
            await asyncio.sleep(wait_time)
        except Exception as e:
            raise FetchError(f"Browser fetch failed for {url}: {e}") from e
        finally:
            await page.close()

        return captured

    async def fetch_rendered_html(self, url: str, wait_selector: str | None = None) -> str:
        """Navigate and return fully rendered HTML."""
        page = await self.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout)
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=settings.browser_timeout)
            return await page.content()
        except Exception as e:
            raise FetchError(f"Browser fetch failed for {url}: {e}") from e
        finally:
            await page.close()

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
