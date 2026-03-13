"""Lightweight HTTP scraper using httpx + BeautifulSoup."""

import asyncio
import json
import random
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from agent.tools.base import BaseTool, ScrapeMetadata, ToolResult
from agent.config import settings

# ---------------------------------------------------------------------------
# User-Agent pool
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

_CF_HEADER_PATTERNS = {"cf-ray", "cf-cache-status", "cf-request-id"}
_CAPTCHA_PATTERNS = re.compile(
    r"(recaptcha|hcaptcha|turnstile|captcha)",
    re.IGNORECASE,
)
_CF_BODY_PATTERNS = re.compile(
    r"(cf-browser-verification|_cf_chl_opt|Just a moment|Checking your browser)",
    re.IGNORECASE,
)
_JSON_VAR_PATTERN = re.compile(
    r'(?:var|let|const)\s+\w+\s*=\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*;',
)


class GeneralScrapeTool(BaseTool):
    """Lightweight HTTP scraper: requests + BeautifulSoup.

    Detects bot protection, extracts HTML tables, embedded JSON, and
    download links.  Falls back gracefully on errors.

    Maintains per-domain cookie jars so session state is preserved across
    sequential requests to the same domain.
    """

    def __init__(self) -> None:
        # Per-domain cookie jars: {domain: httpx.Cookies}
        self._cookie_jars: dict[str, httpx.Cookies] = {}

    def _pick_user_agent(self) -> str:
        return random.choice(_USER_AGENTS)

    def _build_headers(self, url: str) -> dict:
        parsed = urlparse(url)
        return {
            "User-Agent": self._pick_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def _fetch(self, url: str, headers: dict) -> httpx.Response:
        """Send an async GET request, reusing per-domain cookies."""
        domain = self._domain(url)
        cookies = self._cookie_jars.get(domain, httpx.Cookies())
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.request_timeout,
            cookies=cookies,
        ) as client:
            response = await client.get(url, headers=headers)
            # Persist cookies back for this domain
            self._cookie_jars[domain] = client.cookies
            return response

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _detect_cloudflare(self, response: httpx.Response, body: str) -> bool:
        has_cf_headers = bool(
            set(k.lower() for k in response.headers.keys()) & _CF_HEADER_PATTERNS
        )
        has_cf_body = bool(_CF_BODY_PATTERNS.search(body))
        return has_cf_headers or (response.status_code == 403 and has_cf_body)

    def _detect_captcha(self, body: str) -> bool:
        return bool(_CAPTCHA_PATTERNS.search(body))

    def _detect_js_required(self, body: str, soup: BeautifulSoup) -> bool:
        """Heuristic: script-heavy page with almost no visible text."""
        text = soup.get_text(separator=" ", strip=True)
        has_scripts = bool(soup.find("script"))
        if has_scripts and len(text) < 100:
            return True
        # Large page but tiny text ratio
        if len(body) > 500 and len(text) < 100:
            return True
        return False

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_tables(self, soup: BeautifulSoup) -> list[list[dict]]:
        """Extract all HTML tables as list-of-dicts."""
        results = []
        for table in soup.find_all("table"):
            headers: list[str] = []
            rows: list[dict] = []
            for i, tr in enumerate(table.find_all("tr")):
                cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                if not cells:
                    continue
                if i == 0 or not headers:
                    headers = cells
                else:
                    if len(cells) == len(headers):
                        rows.append(dict(zip(headers, cells)))
            if rows:
                results.append(rows)
        return results

    def _extract_json_data(self, soup: BeautifulSoup) -> Any:
        """Extract JSON from <script type='application/json'> or JS variable assignments."""
        # 1. application/json script tags
        for tag in soup.find_all("script", type="application/json"):
            try:
                return json.loads(tag.string)
            except (json.JSONDecodeError, TypeError):
                continue

        # 2. JS variable assignments containing arrays/objects
        for tag in soup.find_all("script", type=lambda t: not t):
            if not tag.string:
                continue
            match = _JSON_VAR_PATTERN.search(tag.string)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None

    def _extract_download_links(self, soup: BeautifulSoup, base_url: str) -> dict[str, list[str]]:
        """Find CSV, XLSX, and PDF download links."""
        csv_links: list[str] = []
        pdf_links: list[str] = []
        for a in soup.find_all("a", href=True):
            href: str = a["href"].lower()
            full_url = urljoin(base_url, a["href"])
            if href.endswith(".csv") or "csv" in href:
                csv_links.append(full_url)
            elif href.endswith(".pdf") or "pdf" in href:
                pdf_links.append(full_url)
        return {"csv": csv_links, "pdf": pdf_links}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(self, url: str, **kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Scrape a URL and return structured data.

        Args:
            url: Target URL to scrape.

        Returns:
            ToolResult with data dict containing tables, json_data, download_links,
            and text; plus ScrapeMetadata in metadata field.
        """
        headers = self._build_headers(url)
        start = time.monotonic()
        try:
            response = await self._fetch(url, headers)
        except Exception as exc:
            return ToolResult(
                success=False,
                data=None,
                error=str(exc),
                metadata={"url": url},
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        body = response.text
        soup = BeautifulSoup(body, "lxml")

        # Detection
        has_cloudflare = self._detect_cloudflare(response, body)
        has_captcha = self._detect_captcha(body)
        is_js_required = self._detect_js_required(body, soup)

        # Extraction
        tables = self._extract_tables(soup)
        json_data = self._extract_json_data(soup)
        download_links = self._extract_download_links(soup, url)
        text = soup.get_text(separator=" ", strip=True)[:4000]

        meta = ScrapeMetadata(
            url=url,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            content_length=len(body),
            has_captcha=has_captcha,
            has_cloudflare=has_cloudflare,
            is_js_required=is_js_required,
            response_time_ms=elapsed_ms,
        )

        data = {
            "tables": tables,
            "json_data": json_data,
            "download_links": download_links,
            "text": text,
        }

        return ToolResult(
            success=True,
            data=data,
            error=None,
            metadata=meta.model_dump(),
        )

    def get_schema(self) -> dict:
        return {
            "name": "general_scrape",
            "description": (
                "Lightweight HTTP scraper using requests + BeautifulSoup. "
                "Use this first before dynamic_scrape. Returns tables, JSON data, "
                "download links, and plain text from a URL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape."},
                },
                "required": ["url"],
            },
        }
