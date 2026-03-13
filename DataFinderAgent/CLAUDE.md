# Scraper Agent — CLAUDE.md

## Project Overview

An intelligent, adaptive web scraping agent that autonomously finds, evaluates, and extracts publicly available data from the web. The agent uses Claude's API with tool use to orchestrate a search → evaluate → scrape → assess → iterate loop. It dynamically adapts its scraping strategy based on page structure, bot protection, and data quality.

**Stack:** Python 3.11+ / FastAPI / CLI interface / Railway deployment
**LLM:** Claude API with native tool use (no LangChain/LangGraph)
**Output formats:** JSON, CSV, Pandas DataFrame

---

## Architecture

```
User (CLI) → Agent Orchestrator → Claude API (tool use)
                                      ↓
                              ┌───────┴────────┐
                              │   Tool Router   │
                              └───┬───┬───┬─────┘
                                  │   │   │
                          search  │   │   │  dynamic_scrape
                                  │   │   │
                            general_scrape │
                                      │
                                  pdf_extract
```

### Core Components

1. **Agent Orchestrator** (`agent/orchestrator.py`) — Main loop. Sends messages to Claude API with tool definitions, processes tool calls, feeds results back. Manages conversation state, loop counting, and user checkpoints.

2. **Tool Definitions** (`agent/tools/`) — Each tool is a Python function with a corresponding Claude tool schema:
   - `web_search` — Find candidate data sources
   - `general_scrape` — Lightweight page recon (requests + BeautifulSoup)
   - `dynamic_scrape` — Full browser scrape (Playwright) for JS-heavy pages
   - `pdf_extract` — Download and parse PDFs
   - `assess_difficulty` — Evaluate scrape complexity and estimate loops

3. **Scrape Strategy Engine** (`agent/strategy.py`) — Analyzes page responses and recommends approach:
   - Detects bot protection (Cloudflare, CAPTCHA, rate limiting)
   - Identifies data format (HTML tables, JSON blobs, CSV downloads, PDFs)
   - Estimates extraction difficulty (1-5 scale)
   - Suggests fallback routes

4. **Output Formatter** (`agent/output.py`) — Converts raw extracted data to JSON, CSV, or DataFrame.

5. **Config & State** (`agent/config.py`, `agent/state.py`) — Runtime config (API keys, timeouts, max loops) and conversation/scrape state tracking.

---

## Key Design Principles

### 1. Dynamic Scraper Adaptation
The agent MUST modify its scraping approach on the fly:
- **Start light:** Always try `requests` + BeautifulSoup first
- **Escalate when needed:** If page returns empty/minimal content, switch to Playwright
- **Header rotation:** Rotate User-Agent strings, accept headers, and referrer on every request
- **Cookie handling:** Maintain session cookies across requests to the same domain
- **Retry with backoff:** Exponential backoff on 429/503 responses (max 3 retries per URL)

### 2. Bot Protection Detection & Avoidance
Before scraping, the agent MUST check for:
- **Cloudflare challenge pages** — Look for `cf-` headers, challenge scripts, 403 with specific body patterns
- **CAPTCHA presence** — Detect reCAPTCHA, hCaptcha, Turnstile script tags or iframes
- **Rate limiting** — Track response codes (429, 503) and `Retry-After` headers
- **JavaScript-required rendering** — Compare raw HTML content length vs. expected data; if raw HTML is mostly empty scripts, flag as JS-required

**Avoidance strategies:**
- Add realistic delays between requests (2-5 seconds, randomized)
- Use residential-style User-Agent strings (Chrome/Firefox on Windows/Mac)
- Set proper `Accept`, `Accept-Language`, `Accept-Encoding` headers
- Include `Referer` header matching the site's domain
- For Cloudflare: try the direct API endpoint if one exists before attempting browser render
- If CAPTCHA detected: DO NOT attempt to solve. Flag to user with difficulty assessment and suggest alternative route.

### 3. Loop Until Output Matches Requirements
The agent operates in a goal-directed loop:
1. User states their data goal (e.g., "MSFT historic monthly returns, last 5 years")
2. Agent searches for sources
3. Agent scrapes candidate source
4. Agent evaluates: Does extracted data match the stated goal?
5. If YES → format and return
6. If NO → diagnose why (wrong data, incomplete, blocked) and either:
   - Drill deeper on current source (follow links, paginate)
   - Pivot to alternative source
   - Ask user for guidance (if difficulty > threshold or loops > limit)

**Loop limits:**
- Default max loops: 10
- User checkpoint at loop 5 (report progress, ask to continue)
- Hard stop at loop 15 with whatever data has been collected
- Each loop tracks: source URL, tool used, data quality score, blocking issues

### 4. Anticipate Issues & Respond
The agent should proactively detect and handle:
- **Empty responses** → Switch from requests to Playwright
- **Partial data** → Look for pagination, "load more" buttons, date range selectors
- **Wrong data format** → Re-parse (e.g., data in JSON blob vs. HTML table)
- **Site down/timeout** → Retry with backoff, then pivot to alternative source
- **PDF instead of HTML** → Route to pdf_extract tool
- **CSV download available** → Prefer direct CSV over page scraping

---

## Development Rules

### Test-First Development
- Write tests BEFORE implementation for every tool and major function
- Use `pytest` for all Python tests
- Test files mirror source structure: `tests/test_orchestrator.py`, `tests/tools/test_web_search.py`, etc.
- Mock external HTTP calls in tests (use `responses` or `pytest-httpx`)
- Every PR must include tests for new functionality

### Code Style
- Type hints on all function signatures
- Docstrings on all public functions (Google style)
- `async` for all I/O-bound operations (HTTP requests, file I/O)
- Use `httpx` for async HTTP (not `requests` for async paths)
- Use `pydantic` for all data models and tool schemas

### Error Handling
- Never let the agent crash on a scrape failure — always catch, log, and let the LLM decide next step
- Structured error returns from all tools: `{"success": bool, "data": Any, "error": str | None, "metadata": dict}`
- Log every tool call and result for debugging

### File Structure
```
scraper-agent/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── Dockerfile
├── railway.toml
├── .env.example
├── agent/
│   ├── __init__.py
│   ├── orchestrator.py      # Main agent loop
│   ├── config.py            # Settings, API keys, limits
│   ├── state.py             # Scrape state tracking
│   ├── strategy.py          # Difficulty assessment, route planning
│   ├── output.py            # JSON/CSV/DataFrame formatting
│   ├── prompts.py           # System prompt and tool descriptions
│   └── tools/
│       ├── __init__.py
│       ├── base.py           # Base tool interface
│       ├── web_search.py     # Search for data sources
│       ├── general_scrape.py # Lightweight HTTP scraper
│       ├── dynamic_scrape.py # Playwright browser scraper
│       └── pdf_extract.py    # PDF download and parse
├── cli/
│   ├── __init__.py
│   └── main.py              # CLI entry point (Click/Typer)
└── tests/
    ├── conftest.py
    ├── test_orchestrator.py
    ├── test_strategy.py
    ├── test_output.py
    └── tools/
        ├── test_web_search.py
        ├── test_general_scrape.py
        ├── test_dynamic_scrape.py
        └── test_pdf_extract.py
```

### Dependencies
```
anthropic          # Claude API client
httpx              # Async HTTP client
beautifulsoup4     # HTML parsing
playwright         # Browser automation (dynamic scraping)
trafilatura        # Content extraction / boilerplate removal
pdfplumber         # PDF text/table extraction
pandas             # DataFrame output
pydantic           # Data models
typer              # CLI framework
rich               # CLI output formatting
python-dotenv      # Env var management
pytest             # Testing
pytest-asyncio     # Async test support
responses          # HTTP mocking for tests
```

---

## System Prompt (for Claude API calls)

The system prompt for the agent's Claude API calls is in `agent/prompts.py`. Key instructions:

1. You are a web scraping agent. Your job is to find and extract specific data from the web.
2. You have tools: web_search, general_scrape, dynamic_scrape, pdf_extract.
3. Always start with web_search to find the best source for the user's data goal.
4. Try general_scrape first (fast, lightweight). Only use dynamic_scrape if general_scrape returns empty/blocked content.
5. After each scrape, evaluate: Does this data match the user's goal? If not, explain why and plan your next step.
6. Track difficulty. If you've tried 3+ sources or 5+ scrape attempts without success, recommend asking the user for guidance.
7. Never attempt to solve CAPTCHAs. If detected, flag it and suggest an alternative route.
8. Prefer direct data endpoints (CSV downloads, API endpoints, JSON feeds) over page scraping when available.
9. Always report what you found, what worked, what didn't, and your confidence in the extracted data.

---

## Environment Variables
```
ANTHROPIC_API_KEY=         # Required
SEARCH_API_KEY=            # For web search (Brave/SerpAPI/Tavily)
SEARCH_PROVIDER=brave      # brave | serpapi | tavily
MAX_LOOPS=10               # Default max agent loops
CHECKPOINT_LOOP=5          # Loop number to checkpoint with user
USER_AGENT_POOL=default    # User-agent rotation pool
REQUEST_DELAY_MIN=2        # Min seconds between requests
REQUEST_DELAY_MAX=5        # Max seconds between requests
LOG_LEVEL=INFO
```

---

## Common Pitfalls & Solutions

| Issue | Solution |
|-------|----------|
| Claude generates tool calls with wrong schema | Validate tool call args with Pydantic before execution |
| Scraper returns HTML boilerplate instead of data | Use trafilatura for content extraction, fall back to Playwright |
| Agent loops endlessly on blocked site | Track failed attempts per domain, hard limit at 3 per domain |
| Context window fills up with scraped HTML | Summarize/truncate scrape results to ~2000 tokens before feeding back |
| Rate limited by target site | Exponential backoff + domain cooldown tracking |
| PDF tables extract as jumbled text | Use pdfplumber with explicit table settings, not just text extraction |
| Agent picks unreliable data source | Prioritize known-good domains in search evaluation (see strategy.py) |
