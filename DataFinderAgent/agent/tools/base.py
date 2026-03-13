"""Base tool interface and shared data models."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class ScrapeMetadata(BaseModel):
    """Metadata captured during a scrape attempt."""

    url: str
    status_code: int = 0
    content_type: str = ""
    content_length: int = 0
    has_captcha: bool = False
    has_cloudflare: bool = False
    is_js_required: bool = False
    response_time_ms: float = 0.0


class ToolResult(BaseModel):
    """Standardised return value from every tool."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class all scraper tools must implement."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool and return a ToolResult."""

    @abstractmethod
    def get_schema(self) -> dict:
        """Return the Claude API tool schema for this tool."""
