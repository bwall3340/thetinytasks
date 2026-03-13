"""Strategy engine — difficulty assessment, source ranking, fallback planning."""

from pydantic import BaseModel

from agent.tools.base import ScrapeMetadata
from agent.state import AgentState

# ---------------------------------------------------------------------------
# Domain reputation (mirrors web_search.py ranking)
# ---------------------------------------------------------------------------

_DOMAIN_SCORES: dict[str, int] = {
    "fred.stlouisfed.org": 10,
    "stockanalysis.com": 9,
    "macrotrends.net": 9,
    "slickcharts.com": 8,
    "finviz.com": 8,
    "barchart.com": 7,
    "finance.yahoo.com": 6,
    "marketwatch.com": 6,
    "wsj.com": 5,
    "reuters.com": 5,
    "bloomberg.com": 5,
}


def _domain_score(url: str) -> int:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lstrip("www.")
    return _DOMAIN_SCORES.get(domain, 0)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DifficultyAssessment(BaseModel):
    """Output of assess_difficulty()."""

    score: int                    # 1 (easy) – 5 (very hard)
    recommended_tool: str         # general_scrape | dynamic_scrape | pdf_extract | alternative_source
    notes: str                    # Human-readable explanation


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StrategyEngine:
    """Assess page difficulty and recommend scraping strategies.

    Also tracks per-domain cooldown timestamps so the agent doesn't
    hammer the same domain repeatedly.
    """

    def __init__(self) -> None:
        import time as _time
        self._last_request_time: dict[str, float] = {}
        self._time = _time

    def record_request(self, url: str) -> None:
        """Record a request timestamp for rate-limit / cooldown tracking."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        self._last_request_time[domain] = self._time.monotonic()

    def is_on_cooldown(self, url: str, cooldown_seconds: float = 2.0) -> bool:
        """Return True if the domain was hit more recently than cooldown_seconds ago."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        last = self._last_request_time.get(domain)
        if last is None:
            return False
        return (self._time.monotonic() - last) < cooldown_seconds

    def assess_difficulty(self, metadata: ScrapeMetadata) -> DifficultyAssessment:
        """Score scrape difficulty 1-5 and recommend the best tool.

        Args:
            metadata: ScrapeMetadata from a previous scrape attempt.

        Returns:
            DifficultyAssessment with score, recommended tool, and notes.
        """
        notes_parts: list[str] = []

        # CAPTCHA = instant hard block
        if metadata.has_captcha:
            return DifficultyAssessment(
                score=5,
                recommended_tool="alternative_source",
                notes="CAPTCHA detected. Cannot proceed. Find an alternative source.",
            )

        score = 1

        # Cloudflare protection
        if metadata.has_cloudflare:
            score = max(score, 4)
            notes_parts.append("Cloudflare protection detected.")

        # Rate limiting
        if metadata.status_code == 429:
            score = max(score, 3)
            notes_parts.append("Rate limited (429). Apply backoff or try later.")

        # JS-required rendering
        if metadata.is_js_required:
            score = max(score, 2)
            notes_parts.append("Page requires JavaScript rendering.")

        # Generic server errors
        if metadata.status_code in (500, 503):
            score = max(score, 3)
            notes_parts.append(f"Server error ({metadata.status_code}).")

        # Determine recommended tool
        if score >= 4:
            recommended_tool = "alternative_source"
        elif metadata.is_js_required:
            recommended_tool = "dynamic_scrape"
        else:
            recommended_tool = "general_scrape"

        notes = " ".join(notes_parts) if notes_parts else "No significant obstacles detected."
        return DifficultyAssessment(score=score, recommended_tool=recommended_tool, notes=notes)

    def rank_sources(self, search_results: list[dict], goal: str) -> list[dict]:
        """Re-rank search results by domain reputation.

        Args:
            search_results: List of {url, title, snippet, domain} dicts.
            goal: User's data goal (reserved for future relevance scoring).

        Returns:
            Sorted list, highest-reputation domains first.
        """
        if not search_results:
            return []
        return sorted(search_results, key=lambda r: _domain_score(r.get("url", "")), reverse=True)

    def suggest_fallback(self, state: AgentState) -> str:
        """Recommend the next best action given the current failure state.

        Args:
            state: Current AgentState.

        Returns:
            A plain-English suggestion string.
        """
        attempts = state.attempts
        if not attempts:
            return "No attempts recorded yet. Start with web_search."

        tools_used = {a.tool_used for a in attempts}
        all_issues = [issue for a in attempts for issue in a.blocking_issues]
        failed_sources = len(state.sources_tried)

        # Too many failures → escalate to user
        if failed_sources >= 5:
            return (
                "Multiple sources have been tried without success. "
                "Recommend user intervention: ask for a specific data source or alternative approach."
            )

        # JS blocking and we haven't tried dynamic yet
        if "is_js_required" in all_issues and "dynamic_scrape" not in tools_used:
            return "Page requires JavaScript. Try dynamic_scrape with Playwright."

        # Cloudflare blocking
        if "cloudflare" in all_issues:
            if "dynamic_scrape" not in tools_used:
                return "Cloudflare detected. Try dynamic_scrape or look for a direct API/CSV endpoint."
            return "Cloudflare blocking both scrapers. Look for an alternative data source or direct API endpoint."

        # Generic: try dynamic if not tried
        if "dynamic_scrape" not in tools_used:
            return "General scrape did not yield results. Escalate to dynamic_scrape."

        return (
            "All standard approaches have been attempted. "
            "Consider an alternative source or ask the user for guidance."
        )
