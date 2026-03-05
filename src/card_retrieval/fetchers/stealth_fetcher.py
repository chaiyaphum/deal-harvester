from __future__ import annotations

import asyncio
import random

import structlog
from playwright.async_api import Browser, Page, Playwright, async_playwright

from card_retrieval.config import settings
from card_retrieval.core.exceptions import FetchError

logger = structlog.get_logger()

# Script to remove webdriver detection flags
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['th-TH', 'th', 'en-US', 'en']});
window.chrome = {runtime: {}};
"""


class StealthFetcher:
    """Playwright fetcher with anti-detection measures for bot-protected sites."""

    def __init__(self, headless: bool | None = None):
        self._headless = headless if headless is not None else settings.browser_headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
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
            timezone_id="Asia/Bangkok",
        )
        await context.add_init_script(STEALTH_SCRIPT)
        return await context.new_page()

    async def _human_like_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _scroll_page(self, page: Page, scrolls: int = 3):
        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
            await self._human_like_delay(0.3, 1.0)

    async def fetch_rendered_html(
        self,
        url: str,
        pre_visit_url: str | None = None,
        wait_selector: str | None = None,
        scroll: bool = True,
    ) -> str:
        page = await self.new_page()
        try:
            # Visit a neutral page first to establish cookies/session
            if pre_visit_url:
                logger.debug("stealth_pre_visit", url=pre_visit_url)
                await page.goto(pre_visit_url, wait_until="domcontentloaded")
                await self._human_like_delay(1.0, 3.0)

            logger.debug("stealth_fetch_start", url=url)
            await page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout)
            await self._human_like_delay(1.0, 2.0)

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=settings.browser_timeout)

            if scroll:
                await self._scroll_page(page)

            return await page.content()
        except Exception as e:
            raise FetchError(f"Stealth fetch failed for {url}: {e}") from e
        finally:
            await page.close()

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
