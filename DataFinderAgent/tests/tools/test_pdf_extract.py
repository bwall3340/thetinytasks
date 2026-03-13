"""Tests for the pdf_extract tool."""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.tools.pdf_extract import PdfExtractTool
from agent.tools.base import ToolResult


def _make_mock_pdf(pages: list[dict]) -> MagicMock:
    """Build a mock pdfplumber PDF object.

    Args:
        pages: list of {text: str, tables: list[list[list[str]]]}
    """
    mock_pages = []
    for p in pages:
        page = MagicMock()
        page.extract_text.return_value = p.get("text", "")
        page.extract_tables.return_value = p.get("tables", [])
        mock_pages.append(page)

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = mock_pages
    return mock_pdf


class TestPdfExtractTool:
    @pytest.fixture
    def tool(self):
        return PdfExtractTool()

    @pytest.fixture
    def mock_http_response(self):
        resp = MagicMock()
        resp.content = b"%PDF fake bytes"
        resp.raise_for_status = MagicMock()
        return resp

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_text_extraction(self, tool, mock_http_response):
        pdf = _make_mock_pdf([{"text": "Annual Revenue 2024", "tables": []}])
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_http_response)

        with patch("agent.tools.pdf_extract.httpx.AsyncClient", return_value=mock_client), \
             patch("agent.tools.pdf_extract.pdfplumber.open", return_value=pdf):
            result: ToolResult = await tool.execute(url="https://example.com/report.pdf")

        assert result.success is True
        assert "Annual Revenue 2024" in result.data["text"]

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_table_extraction(self, tool, mock_http_response):
        raw_table = [
            ["Date", "Revenue"],
            ["2024-Q1", "100B"],
            ["2024-Q2", "105B"],
        ]
        pdf = _make_mock_pdf([{"text": "", "tables": [raw_table]}])
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_http_response)

        with patch("agent.tools.pdf_extract.httpx.AsyncClient", return_value=mock_client), \
             patch("agent.tools.pdf_extract.pdfplumber.open", return_value=pdf):
            result: ToolResult = await tool.execute(url="https://example.com/report.pdf")

        assert result.success is True
        tables = result.data["tables"]
        assert len(tables) == 1
        assert tables[0][0]["Date"] == "2024-Q1"
        assert tables[0][0]["Revenue"] == "100B"

    # ------------------------------------------------------------------
    # Multi-page
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_multi_page_text_concatenated(self, tool, mock_http_response):
        pdf = _make_mock_pdf([
            {"text": "Page one content.", "tables": []},
            {"text": "Page two content.", "tables": []},
        ])
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_http_response)

        with patch("agent.tools.pdf_extract.httpx.AsyncClient", return_value=mock_client), \
             patch("agent.tools.pdf_extract.pdfplumber.open", return_value=pdf):
            result: ToolResult = await tool.execute(url="https://example.com/report.pdf")

        assert "Page one content." in result.data["text"]
        assert "Page two content." in result.data["text"]
        assert result.metadata["pages"] == 2

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_download_failure_returns_failure(self, tool):
        import httpx as httpx_module
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx_module.TimeoutException("timeout"))

        with patch("agent.tools.pdf_extract.httpx.AsyncClient", return_value=mock_client):
            result: ToolResult = await tool.execute(url="https://example.com/report.pdf")

        assert result.success is False
        assert result.error is not None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def test_schema(self, tool):
        schema = tool.get_schema()
        assert schema["name"] == "pdf_extract"
        assert "url" in schema["input_schema"]["required"]
