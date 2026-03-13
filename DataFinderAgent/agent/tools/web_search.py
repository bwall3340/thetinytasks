"""Web search tool — find candidate data sources via Brave, SerpAPI, or Tavily."""

from typing import Any
from urllib.parse import urlparse

import httpx

from agent.tools.base import BaseTool, ToolResult
from agent.config import settings

# ---------------------------------------------------------------------------
# Domain reputation: higher score = better financial data source
# ---------------------------------------------------------------------------

_DOMAIN_SCORES: dict[str, int] = {
    "fred.stlouisfed.org": 10,
    "stockanalysis.com": 9,
    "macrotrends.net": 9,
    "slickcharts.com": 8,
    "finviz.com": 8,
    "barchart.com": 7,
    "wisesheets.io": 7,
    "finance.yahoo.com": 6,
    "marketwatch.com": 6,
    "wsj.com": 5,
    "reuters.com": 5,
    "bloomberg.com": 5,
}


def _domain_score(url: str) -> int:
    domain = urlparse(url).netloc.lstrip("www.")
    return _DOMAIN_SCORES.get(domain, 0)


class WebSearchTool(BaseTool):
    """Search for data sources using Brave, SerpAPI, or Tavily.

    Results are ranked by domain reputation so the agent prefers
    known-good financial data sites.
    """

    def __init__(self) -> None:
        self.provider: str = settings.search_provider
        self.api_key: str = settings.search_api_key

    # ------------------------------------------------------------------
    # Provider API calls
    # ------------------------------------------------------------------

    async def _call_api(self, query: str) -> dict:
        """Dispatch to the configured search provider and return raw JSON."""
        if self.provider == "brave":
            return await self._brave(query)
        elif self.provider == "serpapi":
            return await self._serpapi(query)
        elif self.provider == "tavily":
            return await self._tavily(query)
        else:
            raise ValueError(f"Unknown search provider: {self.provider}")

    async def _brave(self, query: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                params={"q": query, "count": 10},
            )
            resp.raise_for_status()
            return resp.json()

    async def _serpapi(self, query: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": self.api_key, "engine": "google", "num": 10},
            )
            resp.raise_for_status()
            return resp.json()

    async def _tavily(self, query: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "api_key": self.api_key, "max_results": 10},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_brave(self, raw: dict) -> list[dict]:
        items = raw.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
                "domain": urlparse(r.get("url", "")).netloc,
            }
            for r in items
        ]

    def _parse_serpapi(self, raw: dict) -> list[dict]:
        items = raw.get("organic_results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "domain": urlparse(r.get("link", "")).netloc,
            }
            for r in items
        ]

    def _parse_tavily(self, raw: dict) -> list[dict]:
        items = raw.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "domain": urlparse(r.get("url", "")).netloc,
            }
            for r in items
        ]

    def _parse(self, raw: dict) -> list[dict]:
        if self.provider == "brave":
            results = self._parse_brave(raw)
        elif self.provider == "serpapi":
            results = self._parse_serpapi(raw)
        elif self.provider == "tavily":
            results = self._parse_tavily(raw)
        else:
            results = []
        # Sort by domain reputation score descending, stable (preserves provider order for ties)
        results.sort(key=lambda r: _domain_score(r["url"]), reverse=True)
        return results

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(self, query: str, **kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Search the web and return ranked results.

        Args:
            query: Natural language search query.

        Returns:
            ToolResult with data as list of {title, url, snippet, domain}.
        """
        try:
            raw = await self._call_api(query)
            results = self._parse(raw)
            return ToolResult(success=True, data=results)
        except Exception as exc:
            return ToolResult(success=False, data=None, error=str(exc))

    def get_schema(self) -> dict:
        return {
            "name": "web_search",
            "description": (
                "Search the web to find URLs that may contain the data you need. "
                "Use this first to discover candidate data sources."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string."},
                },
                "required": ["query"],
            },
        }
