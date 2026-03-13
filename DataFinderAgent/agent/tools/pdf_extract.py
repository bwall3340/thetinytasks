"""PDF download and text/table extraction tool."""

import io
from typing import Any

import httpx
import pdfplumber

from agent.tools.base import BaseTool, ToolResult


class PdfExtractTool(BaseTool):
    """Downloads a PDF and extracts text and tables using pdfplumber."""

    async def execute(self, url: str, **kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Download a PDF and extract its content.

        Args:
            url: Direct URL to the PDF file.

        Returns:
            ToolResult with data = {"text": str, "tables": list[list[dict]]}.
        """
        from agent.tools.general_scrape import GeneralScrapeTool
        from agent.config import settings

        helper = GeneralScrapeTool()
        headers = helper._build_headers(url)

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                pdf_bytes = resp.content

            tables: list[list[dict]] = []
            text_parts: list[str] = []

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
                    raw_tables = page.extract_tables()
                    for raw in (raw_tables or []):
                        if not raw:
                            continue
                        headers_row = [str(c or "") for c in raw[0]]
                        rows = [
                            dict(zip(headers_row, [str(c or "") for c in row]))
                            for row in raw[1:]
                        ]
                        if rows:
                            tables.append(rows)

            return ToolResult(
                success=True,
                data={"text": "\n".join(text_parts), "tables": tables},
                metadata={"url": url, "pages": len(text_parts)},
            )

        except Exception as exc:
            return ToolResult(success=False, data=None, error=str(exc), metadata={"url": url})

    def get_schema(self) -> dict:
        return {
            "name": "pdf_extract",
            "description": "Download a PDF from a URL and extract its text and tables.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the PDF file."},
                },
                "required": ["url"],
            },
        }
