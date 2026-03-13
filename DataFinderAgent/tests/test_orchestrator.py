"""Tests for the ScraperAgent orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.orchestrator import ScraperAgent
from agent.tools.base import ToolResult
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Helpers — fake Claude API responses
# ---------------------------------------------------------------------------

def _tool_use_message(tool_name: str, tool_input: dict, tool_use_id: str = "tu_001") -> MagicMock:
    """Simulate a Claude response that requests a tool call."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_use_id

    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [block]
    return msg


def _text_message(text: str) -> MagicMock:
    """Simulate a Claude response with plain text (goal met)."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [block]
    return msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestToolRouting:
    @pytest.fixture
    def agent(self):
        return ScraperAgent()

    @pytest.mark.asyncio
    async def test_routes_web_search(self, agent):
        with patch.object(agent.tools["web_search"], "execute", new_callable=AsyncMock) as mock:
            mock.return_value = ToolResult(success=True, data=[])
            result = await agent._execute_tool("web_search", {"query": "test"})
        mock.assert_called_once_with(query="test")
        assert isinstance(result, ToolResult)

    @pytest.mark.asyncio
    async def test_routes_general_scrape(self, agent):
        with patch.object(agent.tools["general_scrape"], "execute", new_callable=AsyncMock) as mock:
            mock.return_value = ToolResult(success=True, data={})
            result = await agent._execute_tool("general_scrape", {"url": "https://example.com"})
        mock.assert_called_once_with(url="https://example.com")

    @pytest.mark.asyncio
    async def test_routes_dynamic_scrape(self, agent):
        with patch.object(agent.tools["dynamic_scrape"], "execute", new_callable=AsyncMock) as mock:
            mock.return_value = ToolResult(success=True, data={})
            await agent._execute_tool("dynamic_scrape", {"url": "https://example.com"})
        mock.assert_called_once_with(url="https://example.com")

    @pytest.mark.asyncio
    async def test_routes_pdf_extract(self, agent):
        with patch.object(agent.tools["pdf_extract"], "execute", new_callable=AsyncMock) as mock:
            mock.return_value = ToolResult(success=True, data={})
            await agent._execute_tool("pdf_extract", {"url": "https://example.com/file.pdf"})
        mock.assert_called_once_with(url="https://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_failure(self, agent):
        result = await agent._execute_tool("nonexistent_tool", {})
        assert result.success is False
        assert result.error is not None


class TestLoopLogic:
    @pytest.fixture
    def agent(self):
        a = ScraperAgent()
        a.state = AgentState(goal="test goal")
        return a

    def test_checkpoint_triggers_at_configured_loop(self, agent):
        from agent.config import settings
        agent.state.current_loop = settings.checkpoint_loop
        assert agent._should_checkpoint() is True

    def test_checkpoint_does_not_trigger_before_configured_loop(self, agent):
        agent.state.current_loop = 2
        assert agent._should_checkpoint() is False

    def test_hard_stop_triggers_at_limit(self, agent):
        from agent.config import settings
        agent.state.current_loop = settings.hard_stop_loop
        assert agent._is_hard_stop() is True

    def test_hard_stop_does_not_trigger_before_limit(self, agent):
        agent.state.current_loop = 5
        assert agent._is_hard_stop() is False


class TestContextSummarization:
    @pytest.fixture
    def agent(self):
        return ScraperAgent()

    def test_large_result_truncated(self, agent):
        big_data = {"text": "x" * 10_000, "tables": []}
        result = ToolResult(success=True, data=big_data)
        summary = agent._summarize_for_context(result)
        # cap is max_content_tokens * 4 chars + truncation suffix (~100 chars)
        assert len(summary) <= (2000 * 4) + 100
        assert "[truncated" in summary

    def test_small_result_not_truncated(self, agent):
        small_data = {"tables": [{"a": 1}], "text": "short"}
        result = ToolResult(success=True, data=small_data)
        summary = agent._summarize_for_context(result)
        assert "short" in summary

    def test_failure_result_includes_error(self, agent):
        result = ToolResult(success=False, data=None, error="Timeout")
        summary = agent._summarize_for_context(result)
        assert "Timeout" in summary


class TestFullLoop:
    """Mock Claude API to test a full search → scrape → return loop."""

    @pytest.mark.asyncio
    async def test_simple_two_step_loop(self):
        agent = ScraperAgent()

        search_result = ToolResult(
            success=True,
            data=[{"url": "https://slickcharts.com/sp500", "title": "SlickCharts", "snippet": "", "domain": "slickcharts.com"}],
        )
        scrape_result = ToolResult(
            success=True,
            data={"tables": [[{"Ticker": "AAPL", "Weight": "7.1"}]], "text": "S&P 500 data"},
        )

        claude_responses = [
            _tool_use_message("web_search", {"query": "S&P 500 constituents"}, "tu_1"),
            _tool_use_message("general_scrape", {"url": "https://slickcharts.com/sp500"}, "tu_2"),
            _text_message("I found the S&P 500 constituent data with ticker AAPL at 7.1% weight."),
        ]

        with patch.object(agent.tools["web_search"], "execute", new_callable=AsyncMock, return_value=search_result), \
             patch.object(agent.tools["general_scrape"], "execute", new_callable=AsyncMock, return_value=scrape_result), \
             patch.object(agent.client.messages, "create", side_effect=claude_responses):
            result = await agent.run("Get the S&P 500 constituent list")

        assert result["success"] is True
        assert result["data"] is not None
        assert agent.state.current_loop <= 3
