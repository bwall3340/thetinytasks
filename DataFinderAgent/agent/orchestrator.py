"""Fan-out agent: search → plan → parallel extract → synthesize."""

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable

import anthropic

from agent.config import settings
from agent.prompts import EXTRACTOR_SYSTEM, PLANNER_SYSTEM, SYNTHESIZER_SYSTEM
from agent.tools.base import ToolResult
from agent.tools.dynamic_scrape import DynamicScrapeTool
from agent.tools.general_scrape import GeneralScrapeTool
from agent.tools.pdf_extract import PdfExtractTool
from agent.tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]


def _parse_json(text: str) -> Any:
    """Extract JSON from text, tolerating markdown code fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
        if match:
            return json.loads(match.group(1))
        raise


class ScraperAgent:
    """Three-phase fan-out agent.

    Phase 1 — Plan:   web search + one Haiku call to select best URLs.
    Phase 2 — Scrape: N parallel sub-agents, each scraping one URL then
                      calling Haiku to extract relevant data.
    Phase 3 — Synth:  one Haiku call to compile summaries into a final report.
    """

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.search_tool = WebSearchTool()
        self.scraper = GeneralScrapeTool()
        self.dynamic_scraper = DynamicScrapeTool()
        self.pdf_extractor = PdfExtractTool()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        goal: str,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        async def emit(phase: str, message: str) -> None:
            logger.info("[%s] %s", phase, message)
            if progress_callback:
                await progress_callback(phase, message)

        # Phase 1 — search
        await emit("planning", "Searching the web for data sources…")
        search_result = await self.search_tool.execute(query=goal)
        if not search_result.success or not search_result.data:
            return {
                "success": False,
                "data": None,
                "summary": f"Search failed: {search_result.error}",
                "sources": [],
            }

        # Phase 1b — plan
        await emit("planning", "Selecting best sources to scrape…")
        candidates = await self._plan(goal, search_result.data)
        await emit("planning", f"Selected {len(candidates)} source(s) to investigate")

        # Phase 2 — parallel scrape + extract
        await emit("scraping", f"Scraping {len(candidates)} source(s) in parallel…")
        tasks = [
            self._scrape_and_extract(goal, c["url"], c.get("intent", ""), emit)
            for c in candidates
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        summaries = [r for r in raw_results if isinstance(r, dict)]

        if not summaries:
            return {
                "success": False,
                "data": None,
                "summary": "All sources failed to scrape.",
                "sources": [],
            }

        found_count = sum(1 for s in summaries if s.get("found"))
        await emit(
            "synthesizing",
            f"Found relevant data in {found_count}/{len(summaries)} source(s). Compiling report…",
        )

        # Phase 3 — synthesize
        result = await self._synthesize(goal, summaries)
        return result

    # ------------------------------------------------------------------
    # Phase 1b — planner
    # ------------------------------------------------------------------

    async def _plan(self, goal: str, search_results: list[dict]) -> list[dict]:
        results_text = json.dumps(search_results[:10], indent=2)
        response = await self.client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            system=[{"type": "text", "text": PLANNER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Goal: {goal}\n\nSearch results:\n{results_text}"}],
        )
        try:
            candidates = _parse_json(response.content[0].text)
            return candidates[: settings.max_sources]
        except Exception:
            logger.warning("Planner returned non-JSON; falling back to top search results")
            return [
                {"url": r["url"], "intent": r.get("snippet", "")}
                for r in search_results[: settings.max_sources]
            ]

    # ------------------------------------------------------------------
    # Phase 2 — per-URL sub-agent
    # ------------------------------------------------------------------

    async def _scrape_and_extract(
        self,
        goal: str,
        url: str,
        intent: str,
        emit: Callable[[str, str], Awaitable[None]],
    ) -> dict:
        await emit("scraping", f"Scraping {url[:70]}…")

        result = await self._fetch(url)

        if not result.success:
            return {
                "url": url,
                "found": False,
                "data": None,
                "summary": f"Scrape failed: {result.error}",
                "confidence": 0.0,
            }

        content = json.dumps(result.data, default=str)
        if len(content) > settings.max_content_chars:
            content = content[: settings.max_content_chars] + "\n… [truncated]"

        try:
            response = await self.client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system=[{"type": "text", "text": EXTRACTOR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{
                    "role": "user",
                    "content": (
                        f"Goal: {goal}\n"
                        f"Intent for this URL: {intent}\n"
                        f"URL: {url}\n\n"
                        f"Scraped content:\n{content}"
                    ),
                }],
            )
            extraction = _parse_json(response.content[0].text)
            extraction["url"] = url
            return extraction
        except Exception as exc:
            logger.warning("Extraction failed for %s: %s", url, exc)
            return {"url": url, "found": False, "data": None, "summary": str(exc), "confidence": 0.0}

    async def _fetch(self, url: str) -> ToolResult:
        """Try general scrape; escalate to dynamic or PDF as needed."""
        if url.lower().endswith(".pdf"):
            return await self.pdf_extractor.execute(url=url)

        result = await self.scraper.execute(url=url)
        if (
            not result.success
            or result.metadata.get("is_js_required")
            or result.metadata.get("has_cloudflare")
        ):
            result = await self.dynamic_scraper.execute(url=url)
        return result

    # ------------------------------------------------------------------
    # Phase 3 — synthesizer
    # ------------------------------------------------------------------

    async def _synthesize(self, goal: str, summaries: list[dict]) -> dict:
        summaries_text = json.dumps(summaries, indent=2, default=str)
        if len(summaries_text) > 8000:
            summaries_text = summaries_text[:8000] + "\n… [truncated]"

        response = await self.client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=[{"type": "text", "text": SYNTHESIZER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": f"Goal: {goal}\n\nFindings from {len(summaries)} source(s):\n{summaries_text}",
            }],
        )
        try:
            return _parse_json(response.content[0].text)
        except Exception:
            text = response.content[0].text
            return {
                "success": any(s.get("found") for s in summaries),
                "data": [s.get("data") for s in summaries if s.get("found")],
                "summary": text,
                "sources": [s.get("url") for s in summaries],
            }
