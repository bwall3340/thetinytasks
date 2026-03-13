# Scraper Agent — Development Plan

## Phase 1: Foundation (Days 1-2)

### Step 1.1: Project Scaffolding
**Goal:** Set up the repo structure, dependencies, and basic config.

- [ ] Initialize project with `pyproject.toml` (use Poetry or pip)
- [ ] Create the full directory structure from CLAUDE.md
- [ ] Set up `.env.example` with all required env vars
- [ ] Create `agent/config.py` with Pydantic Settings model
- [ ] Create `Dockerfile` and `railway.toml` for Railway deployment
- [ ] Install all dependencies, verify imports
- [ ] Set up pytest config in `pyproject.toml`

**Deliverable:** Running `pytest` returns 0 errors (no tests yet, just clean setup).

---

### Step 1.2: Data Models & Tool Interface
**Goal:** Define the contracts that all tools and the orchestrator will use.

- [ ] Create `agent/tools/base.py`:
  - `ToolResult` Pydantic model: `{"success": bool, "data": Any, "error": str | None, "metadata": dict}`
  - `ScrapeMetadata` model: `{"url": str, "status_code": int, "content_type": str, "content_length": int, "has_captcha": bool, "has_cloudflare": bool, "is_js_required": bool, "response_time_ms": float}`
  - Base `Tool` abstract class with `execute()` and `get_schema()` methods
- [ ] Create `agent/state.py`:
  - `ScrapeAttempt` model tracking each tool call (url, tool_used, result_quality, blocking_issues)
  - `AgentState` model tracking overall progress (goal, attempts list, current_loop, sources_tried, best_data_so_far)
- [ ] Create `agent/output.py`:
  - `OutputFormatter` class with `to_json()`, `to_csv()`, `to_dataframe()` methods

**Tests to write FIRST:**
- `tests/test_output.py` — Test conversion of sample data dicts to all three formats
- `tests/tools/test_base.py` — Test ToolResult validation, ScrapeMetadata detection flags

**Deliverable:** All data models validate correctly, output formatter converts sample data.

---

### Step 1.3: General Scrape Tool
**Goal:** Build the lightweight HTTP scraper — this is the workhorse tool.

- [ ] Create `agent/tools/general_scrape.py`:
  - Accept URL, optional CSS selectors, optional content type hint
  - Use `httpx` (async) to fetch the page
  - Parse response headers for bot protection signals (Cloudflare headers, CAPTCHA indicators)
  - Extract content using `trafilatura` for article/text content
  - Extract HTML tables using BeautifulSoup → list of dicts
  - Look for embedded JSON data (script tags with `application/json` or known variable patterns)
  - Look for direct download links (CSV, XLSX, PDF)
  - Return `ToolResult` with extracted data + `ScrapeMetadata`
  - Implement User-Agent rotation from a pool of realistic browser strings
  - Add randomized delay (configurable min/max)

**Tests to write FIRST:**
- `tests/tools/test_general_scrape.py`:
  - Test HTML table extraction from a mock HTML page
  - Test JSON blob extraction from mock page with embedded script data
  - Test Cloudflare detection (mock 403 with cf- headers)
  - Test CAPTCHA detection (mock page with reCAPTCHA script tag)
  - Test CSV link detection
  - Test User-Agent rotation (verify it changes across calls)
  - Test empty page detection (flags `is_js_required`)

**Deliverable:** General scraper handles clean HTML pages, detects protection, returns structured results.

---

## Phase 2: Intelligence Layer (Days 3-4)

### Step 2.1: Web Search Tool
**Goal:** Give the agent the ability to find data sources.

- [ ] Create `agent/tools/web_search.py`:
  - Support multiple search providers (Brave, SerpAPI, Tavily) via config
  - Accept search query string
  - Return top N results with: title, URL, snippet, domain
  - Filter/rank results by domain reliability (prefer known financial data sites)
  - Return `ToolResult` with search results

**Tests to write FIRST:**
- `tests/tools/test_web_search.py`:
  - Test query formatting for each provider
  - Test result parsing from mock API responses
  - Test domain ranking (financial sites ranked higher)

**Deliverable:** Search tool returns structured results from at least one provider.

---

### Step 2.2: Strategy Engine
**Goal:** Build the brain that assesses difficulty and recommends next steps.

- [ ] Create `agent/strategy.py`:
  - `assess_difficulty(metadata: ScrapeMetadata) -> DifficultyAssessment`:
    - Score 1-5 based on: bot protection, JS requirement, data structure complexity
    - Estimate loops remaining
    - Recommend tool (general vs. dynamic vs. alternative source)
  - `rank_sources(search_results: list, goal: str) -> list`:
    - Prioritize by: domain reputation, data format likelihood, scrape friendliness
    - Known-good domains list for financial data (stockanalysis.com, macrotrends.net, finviz, FRED, etc.)
  - `suggest_fallback(state: AgentState) -> str`:
    - Based on what's been tried, suggest next best approach
    - If all routes exhausted, recommend user intervention

**Tests to write FIRST:**
- `tests/test_strategy.py`:
  - Test difficulty scoring for various metadata combinations
  - Test source ranking with financial domain preferences
  - Test fallback suggestions based on different failure states

**Deliverable:** Strategy engine scores difficulty accurately and ranks sources intelligently.

---

### Step 2.3: Agent Orchestrator (Core Loop)
**Goal:** Wire up the main agent loop with Claude API tool use.

- [ ] Create `agent/prompts.py`:
  - System prompt (from CLAUDE.md spec)
  - Tool definitions in Claude API schema format
  - User message template that includes the data goal and current state

- [ ] Create `agent/orchestrator.py`:
  - `ScraperAgent` class:
    - `__init__`: Set up Anthropic client, load tool definitions, initialize state
    - `run(goal: str) -> AgentResult`: Main loop
      1. Send goal + state to Claude API with tools
      2. Process tool_use response blocks
      3. Execute requested tool
      4. Feed tool result back to Claude
      5. Check if Claude says goal is met → format and return
      6. Check loop count → checkpoint with user at configured interval
      7. Check hard stop → return best data so far
    - `_execute_tool(name, args) -> ToolResult`: Route tool calls to implementations
    - `_should_checkpoint() -> bool`: Check if user input needed
    - `_summarize_for_context(result: ToolResult) -> str`: Truncate large scrape results

**Tests to write FIRST:**
- `tests/test_orchestrator.py`:
  - Test tool routing (correct tool called for each name)
  - Test loop counting and checkpoint logic
  - Test hard stop behavior
  - Test context summarization (large results get truncated)
  - Mock Claude API responses to test full loop (search → scrape → evaluate → return)

**Deliverable:** Agent can run a complete search → scrape → return loop for a simple case.

---

## Phase 3: Dynamic Capabilities (Days 5-6)

### Step 3.1: Dynamic Scrape Tool (Playwright)
**Goal:** Handle JavaScript-heavy pages that the general scraper can't parse.

- [ ] Create `agent/tools/dynamic_scrape.py`:
  - Launch headless Chromium via Playwright
  - Navigate to URL with realistic viewport and headers
  - Wait for content to render (smart wait: network idle + DOM stability check)
  - Extract rendered HTML, then parse same as general scraper
  - Handle common patterns: "Load More" buttons, infinite scroll, date pickers
  - Screenshot capability for debugging
  - Proper cleanup (close browser context after each scrape)
  - Timeout handling (30 second max per page)

**Tests to write FIRST:**
- `tests/tools/test_dynamic_scrape.py`:
  - Test with a local HTML file that requires JS rendering
  - Test timeout handling
  - Test cleanup (browser context closed)
  - Test screenshot output

**Deliverable:** Dynamic scraper renders JS pages and extracts content.

---

### Step 3.2: PDF Extract Tool
**Goal:** Download and parse PDFs that contain financial data.

- [ ] Create `agent/tools/pdf_extract.py`:
  - Download PDF from URL (with same header/delay protections)
  - Extract text using pdfplumber
  - Extract tables using pdfplumber table detection
  - Handle multi-page documents (concatenate or paginate results)
  - Return structured data (tables as list of dicts, text as string)

**Tests to write FIRST:**
- `tests/tools/test_pdf_extract.py`:
  - Test table extraction from a sample financial PDF
  - Test text extraction
  - Test multi-page handling
  - Test download failure handling

**Deliverable:** PDF tool extracts tables and text from financial documents.

---

### Step 3.3: Bot Protection Avoidance Enhancements
**Goal:** Make the agent more resilient against common protections.

- [ ] Enhance `agent/tools/general_scrape.py`:
  - Cookie jar persistence across requests to same domain
  - Referrer chain building (visit homepage → navigate to data page)
  - Detection of JavaScript challenge pages (Cloudflare "checking your browser")
  - Auto-escalation: if general scrape detects JS challenge, flag for dynamic scraper
- [ ] Add to `agent/strategy.py`:
  - Domain-specific knowledge: known protections per site
  - Cooldown tracking: don't hit same domain more than once per N seconds
  - Alternative URL patterns (try API endpoints, mobile versions, cached versions)

**Tests to write FIRST:**
- Test cookie persistence across sequential requests
- Test referrer chain building
- Test JS challenge detection
- Test cooldown enforcement

**Deliverable:** Agent gracefully handles and works around common bot protections.

---

## Phase 4: CLI & Polish (Days 7-8)

### Step 4.1: CLI Interface
**Goal:** Clean terminal interface for interacting with the agent.

- [ ] Create `cli/main.py` using Typer + Rich:
  - `scrape` command: Takes goal string, optional output format, optional max loops
  - Rich console output showing agent progress:
    - Current loop number
    - Tool being used
    - Source being scraped
    - Difficulty assessment
    - Data quality score
  - User checkpoint prompts (continue / try different route / stop)
  - Final output display (table preview for DataFrames, file path for CSV/JSON)
  - `--verbose` flag for full tool call logging
  - `--output` flag for file output path

**Deliverable:** User can run `python -m cli.main scrape "MSFT historic returns last 5 years" --format csv --output msft_returns.csv`

---

### Step 4.2: Railway Deployment Setup
**Goal:** Deployable to Railway as a long-running service or CLI tool.

- [ ] Finalize `Dockerfile`:
  - Python 3.11 slim base
  - Install Playwright browsers
  - Copy source and install deps
  - Entrypoint configurable (CLI or FastAPI)
- [ ] Create `railway.toml` with build and deploy config
- [ ] Add health check endpoint (FastAPI) for future API mode
- [ ] Environment variable configuration in Railway dashboard

**Deliverable:** Agent deploys and runs on Railway.

---

### Step 4.3: Integration Testing with Real Sites
**Goal:** Validate the full pipeline against real-world targets.

- [ ] Run all test use cases from the test plan (see below)
- [ ] Document success/failure for each case
- [ ] Fix issues discovered during integration testing
- [ ] Add any new edge case handling

**Deliverable:** Agent successfully completes at least 4 of 6 test use cases.

---

## Test Use Cases

These are ordered by difficulty and should be used to validate the agent incrementally.

### Test 1: SlickCharts — S&P 500 Constituents (Difficulty: 1/5)
**Goal:** "Get the current S&P 500 constituent list with ticker symbols and weights"
**Why this is easy:** SlickCharts serves clean HTML tables, no JS rendering needed, no bot protection.
**Expected route:** web_search → find slickcharts.com → general_scrape → extract HTML table → done in 2-3 loops.
**Expected output:** DataFrame with ~503 rows (ticker, company, weight).
**Success criteria:** All 500+ tickers present, weights sum to ~100%.

---

### Test 2: Stockanalysis.com — MSFT Historical Prices (Difficulty: 2/5)
**Goal:** "Get Microsoft (MSFT) monthly closing prices for the last 5 years"
**Why this is moderate:** Server-rendered HTML, data is in clean tables, but may need to navigate to the right page (History tab) and handle pagination or date filtering.
**Expected route:** web_search → find stockanalysis.com/stocks/msft/history → general_scrape → extract table → may need to adjust URL params for date range → 3-5 loops.
**Expected output:** DataFrame with ~60 rows (date, open, high, low, close, volume).
**Success criteria:** ~60 months of data, all price columns present, dates are sequential.

---

### Test 3: Macrotrends.net — AAPL Revenue History (Difficulty: 2/5)
**Goal:** "Get Apple's quarterly revenue for the last 10 years"
**Why this is moderate:** Data is embedded in JavaScript variables on the page, not in plain HTML tables. The general scraper needs to detect and extract the JS-embedded data.
**Expected route:** web_search → find macrotrends.net/stocks/charts/AAPL/apple/revenue → general_scrape → detect JS data → extract from script tag → parse JSON → 3-5 loops.
**Expected output:** DataFrame with ~40 rows (date, revenue).
**Success criteria:** ~40 quarters of data, revenue values are numeric and reasonable.

---

### Test 4: FRED — Federal Funds Rate History (Difficulty: 2/5)
**Goal:** "Get the Federal Funds Effective Rate monthly data for the last 20 years"
**Why this is easy-moderate:** FRED has direct CSV download links. Agent should detect the download option rather than scraping the chart page.
**Expected route:** web_search → find FRED series page → general_scrape → detect CSV download link → download CSV directly → parse → 2-4 loops.
**Expected output:** DataFrame with ~240 rows (date, rate).
**Success criteria:** Agent discovers and uses the CSV download rather than scraping the page. Data spans 20 years.

---

### Test 5: Finviz — Technology Sector Screen (Difficulty: 3/5)
**Goal:** "Get a list of technology stocks with market cap over $10B, including P/E ratio and market cap"
**Why this is moderate-hard:** Finviz has mild bot protection and paginated results (20 per page). Agent needs to detect pagination and loop through pages.
**Expected route:** web_search → find finviz screener → general_scrape → extract first page → detect pagination → scrape additional pages → combine results → 5-8 loops.
**Expected output:** DataFrame with 50-100+ rows (ticker, company, sector, market_cap, pe_ratio).
**Success criteria:** Agent handles pagination, collects multiple pages, data is clean and complete.

---

### Test 6: Yahoo Finance — Portfolio Returns (Difficulty: 4/5)
**Goal:** "Get 1-year daily returns for a portfolio: AAPL, MSFT, GOOGL, AMZN, NVDA"
**Why this is hard:** Yahoo has aggressive bot protection, may require dynamic scraping or finding the CSV download endpoint. Multiple tickers means multiple requests with rate limiting risk.
**Expected route:** web_search → find yahoo finance → general_scrape → likely blocked or JS-required → escalate to dynamic_scrape or find CSV endpoint → loop per ticker with delays → 8-12 loops.
**Expected output:** DataFrame with ~252 rows × 5 ticker columns (daily returns).
**Success criteria:** Agent detects bot protection, adapts strategy, successfully extracts data for all 5 tickers. May require fallback to alternative source — that's OK.

---

## Success Metrics for MVP

1. **Test pass rate:** ≥ 4 of 6 test cases succeed end-to-end
2. **Adaptability:** Agent switches tools at least once during a hard test case
3. **User communication:** Agent provides clear progress updates and checkpoint prompts
4. **Error resilience:** Agent never crashes, always returns partial data or clear error
5. **Output quality:** Extracted data is clean, properly typed, and matches the stated goal
