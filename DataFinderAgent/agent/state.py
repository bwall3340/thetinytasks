"""Scrape state tracking models."""

from typing import Any
from pydantic import BaseModel, Field


class ScrapeAttempt(BaseModel):
    """Record of a single tool invocation."""

    loop: int
    url: str
    tool_used: str
    result_quality: float = 0.0   # 0.0 – 1.0 subjective score
    blocking_issues: list[str] = Field(default_factory=list)
    rows_extracted: int = 0
    error: str | None = None


class AgentState(BaseModel):
    """Tracks overall agent progress across the run."""

    goal: str
    current_loop: int = 0
    attempts: list[ScrapeAttempt] = Field(default_factory=list)
    sources_tried: list[str] = Field(default_factory=list)
    domain_attempt_counts: dict[str, int] = Field(default_factory=dict)
    best_data_so_far: Any = None
    best_quality_score: float = 0.0
    goal_met: bool = False

    def record_attempt(self, attempt: ScrapeAttempt) -> None:
        """Append an attempt and update domain tracking."""
        self.attempts.append(attempt)
        if attempt.url not in self.sources_tried:
            self.sources_tried.append(attempt.url)
        from urllib.parse import urlparse
        domain = urlparse(attempt.url).netloc
        self.domain_attempt_counts[domain] = self.domain_attempt_counts.get(domain, 0) + 1

    def domain_attempts(self, url: str) -> int:
        """Return how many times we've hit the domain of the given URL."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return self.domain_attempt_counts.get(domain, 0)
