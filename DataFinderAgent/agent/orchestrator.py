"""Main agent loop — orchestrates Claude API tool use."""

import json
import logging
from typing import Any

import anthropic

from agent.config import settings
from agent.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from agent.state import AgentState, ScrapeAttempt
from agent.tools.base import ToolResult
from agent.tools.web_search import WebSearchTool
from agent.tools.general_scrape import GeneralScrapeTool
from agent.tools.dynamic_scrape import DynamicScrapeTool
from agent.tools.pdf_extract import PdfExtractTool

logger = logging.getLogger(__name__)


class ScraperAgent:
    """Orchestrates the search → scrape → evaluate → iterate loop.

    Uses Claude's tool-use API to autonomously find and extract data.
    """

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.tools: dict[str, Any] = {
            "web_search": WebSearchTool(),
            "general_scrape": GeneralScrapeTool(),
            "dynamic_scrape": DynamicScrapeTool(),
            "pdf_extract": PdfExtractTool(),
        }
        self.state: AgentState = AgentState(goal="")
        self._messages: list[dict] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, goal: str) -> dict:
        """Run the agent to completion for the given data goal.

        Args:
            goal: Natural language description of the data to extract.

        Returns:
            dict with keys: success (bool), data (Any), summary (str), loops (int).
        """
        self.state = AgentState(goal=goal)
        self._messages = [{"role": "user", "content": goal}]

        while True:
            self.state.current_loop += 1
            logger.info("Loop %d", self.state.current_loop)

            if self._is_hard_stop():
                logger.warning("Hard stop reached at loop %d", self.state.current_loop)
                return {
                    "success": self.state.best_data_so_far is not None,
                    "data": self.state.best_data_so_far,
                    "summary": f"Hard stop at loop {self.state.current_loop}. Returning best data collected.",
                    "loops": self.state.current_loop,
                }

            if self._should_checkpoint():
                logger.info("Checkpoint at loop %d", self.state.current_loop)
                # In CLI mode the caller handles user prompting; here we log and continue.

            # Call Claude
            response = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self._messages,
            )

            # Append assistant message
            self._messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Claude is done — extract final text
                text = next(
                    (b.text for b in response.content if b.type == "text"),
                    "Done.",
                )
                return {
                    "success": True,
                    "data": self.state.best_data_so_far,
                    "summary": text,
                    "loops": self.state.current_loop,
                }

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    tool_result = await self._execute_tool(block.name, block.input)
                    self._update_state(block.name, block.input, tool_result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": self._summarize_for_context(tool_result),
                    })
                self._messages.append({"role": "user", "content": tool_results})

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, args: dict) -> ToolResult:
        """Route a tool call to its implementation.

        Args:
            name: Tool name from Claude's tool_use block.
            args: Tool arguments dict.

        Returns:
            ToolResult from the tool.
        """
        tool = self.tools.get(name)
        if tool is None:
            return ToolResult(success=False, data=None, error=f"Unknown tool: {name}")
        try:
            return await tool.execute(**args)
        except Exception as exc:
            logger.exception("Tool %s raised an exception", name)
            return ToolResult(success=False, data=None, error=str(exc))

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def _update_state(self, tool_name: str, args: dict, result: ToolResult) -> None:
        """Record a tool invocation in agent state."""
        url = args.get("url", args.get("query", ""))
        blocking_issues: list[str] = []
        if result.metadata.get("has_captcha"):
            blocking_issues.append("captcha")
        if result.metadata.get("has_cloudflare"):
            blocking_issues.append("cloudflare")
        if result.metadata.get("is_js_required"):
            blocking_issues.append("is_js_required")

        # Rough quality score based on data presence
        quality = 0.0
        if result.success and result.data:
            data = result.data
            if isinstance(data, list) and data:
                quality = min(1.0, len(data) / 10)
            elif isinstance(data, dict):
                tables = data.get("tables", [])
                json_data = data.get("json_data")
                quality = 0.5 if (tables or json_data) else 0.1

        attempt = ScrapeAttempt(
            loop=self.state.current_loop,
            url=url,
            tool_used=tool_name,
            result_quality=quality,
            blocking_issues=blocking_issues,
        )
        self.state.record_attempt(attempt)

        if quality > self.state.best_quality_score and result.data:
            self.state.best_data_so_far = result.data
            self.state.best_quality_score = quality

    # ------------------------------------------------------------------
    # Loop control
    # ------------------------------------------------------------------

    def _should_checkpoint(self) -> bool:
        """Return True if we've hit the checkpoint loop count."""
        return self.state.current_loop == settings.checkpoint_loop

    def _is_hard_stop(self) -> bool:
        """Return True if we've reached the hard stop loop count."""
        return self.state.current_loop >= settings.hard_stop_loop

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def _summarize_for_context(self, result: ToolResult) -> str:
        """Truncate large tool results to avoid filling the context window.

        Args:
            result: ToolResult from a tool call.

        Returns:
            String representation, capped at ~2000 chars.
        """
        if not result.success:
            return f"Tool failed: {result.error}"

        raw = json.dumps(result.data, default=str)
        cap = settings.max_content_tokens * 4  # rough char estimate
        if len(raw) > cap:
            return raw[:cap] + f"\n... [truncated, total {len(raw)} chars]"
        return raw
