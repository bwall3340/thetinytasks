"""Tests for web_search tool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.tools.web_search import WebSearchTool
from agent.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Mock API responses
# ---------------------------------------------------------------------------

BRAVE_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "S&P 500 Historical Data - Macrotrends",
                "url": "https://www.macrotrends.net/2526/sp-500-historical-annual-returns",
                "description": "S&P 500 historical annual returns going back to 1928.",
            },
            {
                "title": "S&P 500 Returns - SlickCharts",
                "url": "https://www.slickcharts.com/sp500/returns",
                "description": "S&P 500 annual total returns since 1928.",
            },
            {
                "title": "S&P 500 Index - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/S%26P_500",
                "description": "The S&P 500 is a stock market index.",
            },
        ]
    }
}

SERPAPI_RESPONSE = {
    "organic_results": [
        {
            "title": "MSFT Historical Prices - Yahoo Finance",
            "link": "https://finance.yahoo.com/quote/MSFT/history",
            "snippet": "Microsoft historical price data.",
        },
        {
            "title": "MSFT Stock History - Stockanalysis",
            "link": "https://stockanalysis.com/stocks/msft/history/",
            "snippet": "Microsoft stock price history.",
        },
    ]
}

TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Federal Funds Rate - FRED",
            "url": "https://fred.stlouisfed.org/series/FEDFUNDS",
            "content": "Federal Funds Effective Rate historical data.",
            "score": 0.92,
        },
    ]
}


class TestWebSearchTool:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    # ------------------------------------------------------------------
    # Provider parsing
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_brave_result_parsing(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = BRAVE_RESPONSE
            with patch.object(tool, "provider", "brave"):
                result: ToolResult = await tool.execute(query="S&P 500 historical returns")

        assert result.success is True
        items = result.data
        assert len(items) == 3
        assert items[0]["title"] == "S&P 500 Historical Data - Macrotrends"
        assert items[0]["url"].startswith("https://")
        assert "snippet" in items[0]
        assert "domain" in items[0]

    @pytest.mark.asyncio
    async def test_serpapi_result_parsing(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = SERPAPI_RESPONSE
            with patch.object(tool, "provider", "serpapi"):
                result: ToolResult = await tool.execute(query="MSFT historical prices")

        assert result.success is True
        items = result.data
        assert len(items) == 2
        # stockanalysis (score 9) should rank above yahoo (score 6)
        assert "stockanalysis.com" in items[0]["domain"]

    @pytest.mark.asyncio
    async def test_tavily_result_parsing(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = TAVILY_RESPONSE
            with patch.object(tool, "provider", "tavily"):
                result: ToolResult = await tool.execute(query="federal funds rate history")

        assert result.success is True
        items = result.data
        assert items[0]["url"] == "https://fred.stlouisfed.org/series/FEDFUNDS"

    # ------------------------------------------------------------------
    # Domain ranking
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_financial_domains_ranked_higher(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = BRAVE_RESPONSE
            with patch.object(tool, "provider", "brave"):
                result: ToolResult = await tool.execute(query="S&P 500 data")

        # macrotrends and slickcharts should rank above wikipedia
        urls = [r["url"] for r in result.data]
        wiki_idx = next(i for i, u in enumerate(urls) if "wikipedia" in u)
        financial_idxes = [i for i, u in enumerate(urls) if "wikipedia" not in u]
        assert all(fi < wiki_idx for fi in financial_idxes)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = Exception("API key invalid")
            result: ToolResult = await tool.execute(query="test")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_empty_results_returns_success_empty_list(self, tool):
        with patch.object(tool, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {"web": {"results": []}}
            with patch.object(tool, "provider", "brave"):
                result: ToolResult = await tool.execute(query="xyzzy nothing found")

        assert result.success is True
        assert result.data == []
