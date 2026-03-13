"""Tests for the dynamic_scrape Playwright tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from agent.tools.dynamic_scrape import DynamicScrapeTool
from agent.tools.base import ToolResult


class TestDynamicScrapeTool:
    @pytest.fixture
    def tool(self):
        return DynamicScrapeTool()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def test_schema_has_required_url(self, tool):
        schema = tool.get_schema()
        assert schema["name"] == "dynamic_scrape"
        assert "url" in schema["input_schema"]["properties"]
        assert "url" in schema["input_schema"]["required"]

    # ------------------------------------------------------------------
    # Happy-path with mocked Playwright
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_tables_from_rendered_html(self, tool):
        HTML = """
        <html><body>
        <table>
          <tr><th>Ticker</th><th>Price</th></tr>
          <tr><td>AAPL</td><td>185</td></tr>
        </table>
        </body></html>
        """
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value=HTML)
        mock_page.wait_for_selector = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw = AsyncMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium = mock_chromium

        with patch("agent.tools.dynamic_scrape.async_playwright", return_value=mock_pw):
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.success is True
        tables = result.data.get("tables", [])
        assert len(tables) >= 1
        assert any(row.get("Ticker") == "AAPL" for row in tables[0])

    @pytest.mark.asyncio
    async def test_wait_for_selector_called_when_provided(self, tool):
        HTML = "<html><body><div id='data'>content</div></body></html>"

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value=HTML)
        mock_page.wait_for_selector = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw = AsyncMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium = mock_chromium

        with patch("agent.tools.dynamic_scrape.async_playwright", return_value=mock_pw):
            await tool.execute(url="https://example.com", wait_for="#data")

        mock_page.wait_for_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_closed_after_scrape(self, tool):
        HTML = "<html><body>text</body></html>"
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value=HTML)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw = AsyncMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium = mock_chromium

        with patch("agent.tools.dynamic_scrape.async_playwright", return_value=mock_pw):
            await tool.execute(url="https://example.com")

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_error_returns_failure(self, tool):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Timeout exceeded"))

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw = AsyncMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium = mock_chromium

        with patch("agent.tools.dynamic_scrape.async_playwright", return_value=mock_pw):
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_metadata_includes_renderer(self, tool):
        HTML = "<html><body><p>data here with enough content to parse</p></body></html>"
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value=HTML)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw = AsyncMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium = mock_chromium

        with patch("agent.tools.dynamic_scrape.async_playwright", return_value=mock_pw):
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.metadata.get("renderer") == "playwright"
