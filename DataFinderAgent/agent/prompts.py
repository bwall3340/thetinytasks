"""System prompt and tool definitions for Claude API calls."""

SYSTEM_PROMPT = """\
You are a web scraping agent. Your job is to find and extract specific data from the web.

You have these tools:
- web_search: Find candidate URLs for the data. ALWAYS start here.
- general_scrape: Lightweight HTTP scrape (fast). Try this first.
- dynamic_scrape: Playwright browser scrape for JS-heavy pages. Escalate if general_scrape returns empty/blocked content.
- pdf_extract: Download and parse PDF files.

Rules:
1. Start every task with web_search to find the best data source.
2. Try general_scrape first. Only use dynamic_scrape if general_scrape returns empty or blocked content.
3. After each scrape evaluate: Does this data match the user's goal? If not, plan your next step.
4. Track difficulty. If you've tried 3+ sources or 5+ scrape attempts without success, stop and tell the user.
5. Never attempt to solve CAPTCHAs. Flag them and suggest an alternative source.
6. Prefer direct data endpoints (CSV downloads, API endpoints, JSON feeds) over page scraping.
7. Always report what you found, what worked, what didn't, and your confidence in the data.
8. Keep scrape results concise when feeding back — summarize large payloads.
"""

TOOL_DEFINITIONS = [
    {
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
    },
    {
        "name": "general_scrape",
        "description": (
            "Lightweight HTTP scraper using requests + BeautifulSoup. "
            "Use this before dynamic_scrape. Returns tables, JSON data, "
            "download links, and plain text from a URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to scrape."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "dynamic_scrape",
        "description": (
            "Full browser scrape using Playwright (Chromium). Use this when "
            "general_scrape returns empty content or detects JS-required rendering."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to scrape."},
                "wait_for": {
                    "type": "string",
                    "description": "Optional CSS selector to wait for before extracting content.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "pdf_extract",
        "description": (
            "Download a PDF from a URL and extract its text and tables."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL of the PDF file to download and parse."},
            },
            "required": ["url"],
        },
    },
]
