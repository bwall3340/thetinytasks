"""Dynamic scraper using Playwright — full browser rendering."""

from typing import Any

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

from agent.tools.base import BaseTool, ToolResult


class DynamicScrapeTool(BaseTool):
    """Playwright-based browser scraper for JS-heavy pages."""

    async def execute(self, url: str, wait_for: str | None = None, **kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Scrape a JS-rendered page with Playwright.

        Args:
            url: Target URL.
            wait_for: Optional CSS selector to wait for before extraction.

        Returns:
            ToolResult with same structure as general_scrape.
        """
        if async_playwright is None:
            return ToolResult(
                success=False,
                data=None,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )

        from agent.config import settings
        from bs4 import BeautifulSoup
        from agent.tools.general_scrape import GeneralScrapeTool
        import time

        helper = GeneralScrapeTool()
        start = time.monotonic()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=helper._pick_user_agent(),
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()
                await page.goto(url, timeout=settings.playwright_timeout, wait_until="networkidle")

                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=settings.playwright_timeout)

                html = await page.content()
                await browser.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            soup = BeautifulSoup(html, "lxml")

            tables = helper._extract_tables(soup)
            json_data = helper._extract_json_data(soup)
            download_links = helper._extract_download_links(soup, url)
            text = soup.get_text(separator=" ", strip=True)[:4000]

            return ToolResult(
                success=True,
                data={
                    "tables": tables,
                    "json_data": json_data,
                    "download_links": download_links,
                    "text": text,
                },
                metadata={
                    "url": url,
                    "response_time_ms": elapsed_ms,
                    "renderer": "playwright",
                },
            )

        except Exception as exc:
            return ToolResult(success=False, data=None, error=str(exc), metadata={"url": url})

    def get_schema(self) -> dict:
        return {
            "name": "dynamic_scrape",
            "description": (
                "Full browser scrape using Playwright (Chromium). Use when "
                "general_scrape returns empty content or detects JS-required rendering."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape."},
                    "wait_for": {
                        "type": "string",
                        "description": "Optional CSS selector to wait for before extracting.",
                    },
                },
                "required": ["url"],
            },
        }
