"""Tests for general_scrape tool (lightweight HTTP scraper)."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from agent.tools.general_scrape import GeneralScrapeTool
from agent.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

HTML_TABLE = """
<html><body>
<table>
  <tr><th>Ticker</th><th>Weight</th></tr>
  <tr><td>AAPL</td><td>7.10</td></tr>
  <tr><td>MSFT</td><td>6.80</td></tr>
</table>
</body></html>
"""

HTML_JSON_BLOB = """
<html><body>
<script type="application/json">{"rows": [{"date": "2024-01", "value": 100}]}</script>
</body></html>
"""

HTML_JSON_VAR = """
<html><body>
<script>
var chartData = [{"date":"2024-01","revenue":100},{"date":"2024-02","revenue":120}];
</script>
</body></html>
"""

HTML_CAPTCHA = """
<html><body>
<script src="https://www.google.com/recaptcha/api.js"></script>
<div class="g-recaptcha"></div>
</body></html>
"""

HTML_CLOUDFLARE = """
<html><body>
<title>Just a moment...</title>
<script>window._cf_chl_opt = {};</script>
</body></html>
"""

HTML_CSV_LINK = """
<html><body>
<a href="/data/fred-rates.csv">Download CSV</a>
<a href="/report.pdf">Annual Report PDF</a>
</body></html>
"""

HTML_EMPTY = "<html><body><script>app.init()</script></body></html>"


def make_response(html: str, status: int = 200, headers: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = html
    resp.content = html.encode()
    resp.headers = httpx.Headers(headers or {"content-type": "text/html"})
    resp.elapsed = MagicMock()
    resp.elapsed.total_seconds.return_value = 0.3
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGeneralScrapeTool:
    @pytest.fixture
    def tool(self):
        return GeneralScrapeTool()

    @pytest.mark.asyncio
    async def test_html_table_extraction(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_TABLE)
            result: ToolResult = await tool.execute(url="https://example.com/table")

        assert result.success is True
        assert isinstance(result.data, dict)
        tables = result.data.get("tables", [])
        assert len(tables) >= 1
        assert any(row.get("Ticker") == "AAPL" for row in tables[0])

    @pytest.mark.asyncio
    async def test_json_blob_extraction(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_JSON_BLOB)
            result: ToolResult = await tool.execute(url="https://example.com/blob")

        assert result.success is True
        json_data = result.data.get("json_data")
        assert json_data is not None

    @pytest.mark.asyncio
    async def test_cloudflare_detection(self, tool):
        cf_headers = {
            "content-type": "text/html",
            "cf-ray": "abc123-EWR",
            "server": "cloudflare",
        }
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_CLOUDFLARE, status=403, headers=cf_headers)
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.metadata.get("has_cloudflare") is True

    @pytest.mark.asyncio
    async def test_captcha_detection(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_CAPTCHA)
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.metadata.get("has_captcha") is True

    @pytest.mark.asyncio
    async def test_csv_link_detection(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_CSV_LINK)
            result: ToolResult = await tool.execute(url="https://example.com")

        csv_links = result.data.get("download_links", {}).get("csv", [])
        assert len(csv_links) >= 1

    @pytest.mark.asyncio
    async def test_pdf_link_detection(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_CSV_LINK)
            result: ToolResult = await tool.execute(url="https://example.com")

        pdf_links = result.data.get("download_links", {}).get("pdf", [])
        assert len(pdf_links) >= 1

    @pytest.mark.asyncio
    async def test_empty_page_flags_js_required(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_EMPTY)
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.metadata.get("is_js_required") is True

    @pytest.mark.asyncio
    async def test_user_agent_rotates(self, tool):
        agents = {tool._pick_user_agent() for _ in range(20)}
        assert len(agents) > 1  # at least 2 different UAs used across 20 picks

    @pytest.mark.asyncio
    async def test_fetch_error_returns_failure(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("timed out")
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_metadata_populated(self, tool):
        with patch.object(tool, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = make_response(HTML_TABLE)
            result: ToolResult = await tool.execute(url="https://example.com")

        assert result.metadata.get("status_code") == 200
        assert result.metadata.get("url") == "https://example.com"
        assert result.metadata.get("response_time_ms") >= 0
