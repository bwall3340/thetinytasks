"""FastAPI web service wrapping the ScraperAgent for the dashboard UI.

Exposes a single SSE endpoint:
    POST /scrape
    Body: {"goal": str, "format": "json" | "csv"}
    Response: text/event-stream — per-loop progress events then a final result event.

Run locally:
    uvicorn api:app --port 8000

Deploy on Railway:
    Set START_COMMAND to: uvicorn api:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.orchestrator import ScraperAgent
from agent.output import OutputFormatter

logger = logging.getLogger(__name__)

app = FastAPI(title="DataFinder Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request / response models ────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    goal: str
    format: Literal["json", "csv"] = "json"


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Encode a dict as an SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


# ── Scrape endpoint ───────────────────────────────────────────────────────────

@app.post("/scrape")
async def scrape(request: ScrapeRequest) -> StreamingResponse:
    """Run the DataFinder agent and stream progress + result via SSE."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress_callback(loop: int, message: str, tool: str | None = None) -> None:
        """Called by the agent at the start of each loop and after each tool use."""
        await queue.put({"type": "progress", "loop": loop, "message": message, "tool": tool})

    async def run_agent() -> None:
        try:
            agent = ScraperAgent()
            # Patch the agent loop to emit progress events
            original_run = agent.run

            async def run_with_progress(goal: str) -> dict:
                agent.state_goal = goal
                result = await _run_agent_with_hooks(agent, goal, progress_callback)
                return result

            result = await run_with_progress(request.goal)

            # Format output
            formatter = OutputFormatter()
            raw_data = result.get("data")
            if request.format == "csv":
                # to_csv expects list[dict]; unwrap if agent returned a dict
                rows = raw_data
                if isinstance(raw_data, dict):
                    # Prefer the first non-empty table, fall back to json_data
                    tables = raw_data.get("tables") or []
                    rows = tables[0] if tables else raw_data.get("json_data") or []
                formatted = formatter.to_csv(rows if isinstance(rows, list) else [])
            else:
                formatted = raw_data

            await queue.put({
                "type": "result",
                "success": result.get("success", False),
                "data": formatted,
                "summary": result.get("summary", ""),
                "loops": result.get("loops", 0),
                "format": request.format,
            })
        except Exception as exc:
            logger.exception("Agent run failed")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # sentinel

    async def event_stream() -> AsyncGenerator[str, None]:
        asyncio.create_task(run_agent())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _sse(item)
        yield _sse_done()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ── Hooked agent run ─────────────────────────────────────────────────────────

async def _run_agent_with_hooks(
    agent: ScraperAgent,
    goal: str,
    progress_callback: Any,
) -> dict:
    """Run the agent loop, injecting progress callbacks around tool calls.

    Rather than modifying orchestrator.py, we monkey-patch _execute_tool
    on this instance to emit events before/after each tool invocation.
    """
    original_execute = agent._execute_tool

    async def hooked_execute(name: str, args: dict):
        url_or_query = args.get("url") or args.get("query") or ""
        short = url_or_query[:80] + ("…" if len(url_or_query) > 80 else "")
        await progress_callback(
            agent.state.current_loop,
            f"Calling {name}" + (f": {short}" if short else ""),
            tool=name,
        )
        result = await original_execute(name, args)
        status = "done" if result.success else f"failed — {result.error or 'unknown error'}"
        await progress_callback(
            agent.state.current_loop,
            f"{name} {status}",
            tool=name,
        )
        return result

    agent._execute_tool = hooked_execute  # type: ignore[method-assign]

    # Also emit a loop-start event by wrapping the outer while loop indirectly:
    # We hook into the state updates instead — emit at each loop start via a
    # patched _should_checkpoint check (which runs at loop start).
    original_is_hard_stop = agent._is_hard_stop

    def hooked_hard_stop() -> bool:
        # Fire-and-forget progress event for loop start (non-blocking)
        loop = agent.state.current_loop
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(
                progress_callback(loop, f"Starting loop {loop}…")
            )
        )
        return original_is_hard_stop()

    agent._is_hard_stop = hooked_hard_stop  # type: ignore[method-assign]

    return await agent.run(goal)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
async def health() -> dict:
    return {"status": "ok", "service": "DataFinder Agent API"}
