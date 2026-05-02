"""FastAPI web service wrapping the ScraperAgent for the dashboard UI.

Exposes a single SSE endpoint:
    POST /scrape
    Body: {"goal": str, "format": "json" | "csv"}
    Response: text/event-stream

    Progress events: {"type": "progress", "phase": str, "message": str}
    Result event:    {"type": "result", "success": bool, "data": any,
                      "summary": str, "sources": list[str], "format": str}
    Error event:     {"type": "error", "message": str}

Run locally:
    uvicorn api:app --port 8000
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.orchestrator import ScraperAgent
from agent.output import OutputFormatter

logger = logging.getLogger(__name__)

app = FastAPI(title="DataFinder Agent API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request model ─────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    goal: str
    format: Literal["json", "csv"] = "json"


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


# ── Scrape endpoint ───────────────────────────────────────────────────────────

@app.post("/scrape")
async def scrape(request: ScrapeRequest) -> StreamingResponse:
    """Run the DataFinder agent and stream progress + result via SSE."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress_callback(phase: str, message: str) -> None:
        await queue.put({"type": "progress", "phase": phase, "message": message})

    async def run_agent() -> None:
        try:
            agent = ScraperAgent()
            result = await agent.run(request.goal, progress_callback=progress_callback)

            formatter = OutputFormatter()
            raw_data = result.get("data")

            if request.format == "csv":
                rows = raw_data
                if isinstance(raw_data, dict):
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
                "sources": result.get("sources", []),
                "format": request.format,
            })
        except Exception as exc:
            logger.exception("Agent run failed")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

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
            "X-Accel-Buffering": "no",
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
async def health() -> dict:
    return {"status": "ok", "service": "DataFinder Agent API"}
