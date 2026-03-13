# The Tiny Tasks - CLAUDE.md

## Project Overview

A multi-tool web application deployed on Railway. The home page is a static frontend; individual tools are either pure client-side HTML/JS or served by a Python Flask backend.

## Repository Structure

```
thetinytasks/
├── index.html              # Home page with tool cards
├── styles.css              # Home page styles (Apple Liquid Glass aesthetic)
├── script.js               # Home page navigation logic
├── data-finder.html        # DataFinder Agent tool UI (SSE streaming, calls DataFinderAgent API)
├── background-remover.html # Background Remover Pro tool (links to WSR backend)
├── return-stream.html      # Return Stream Digitizer tool (pure client-side HTML)
├── Sankey/                 # Sankey Chart tool (pure client-side HTML)
│   └── sankey_chart_tool (15).html
├── WhiteBackgroundRemover/ # Simple client-side white bg remover
├── WSR/                    # Flask backend for vectorizer/background remover
│   ├── app.py              # Flask app, all routes defined here
│   ├── vectorizer_engine.py
│   ├── detailed_vectorizer.py
│   ├── extreme_vectorizer.py
│   ├── test_vectorizer.py  # AdvancedTestVectorizer class (NOT a test file)
│   ├── logo_upscaler.py
│   ├── requirements.txt
│   └── tests/              # Pytest test suite
│       ├── conftest.py
│       └── test_app.py
├── DataFinderAgent/        # AI web scraping agent (separate Railway service)
│   ├── CLAUDE.md           # Full architecture spec for the agent
│   ├── api.py              # FastAPI SSE wrapper — exposes POST /scrape
│   ├── agent/              # Orchestrator, tools, strategy engine, output formatter
│   ├── cli/                # Typer CLI entry point
│   └── pyproject.toml      # Dependencies (anthropic, fastapi, playwright, etc.)
├── Dockerfile              # Builds WSR/ Flask app
└── railway.toml            # Railway deployment config
```

## Tech Stack

- **Frontend**: Vanilla HTML, CSS, JavaScript (no framework)
- **Backend**: Python 3.11, Flask 3.0, gunicorn
- **Image processing**: OpenCV, Pillow, scikit-image, scipy, numpy
- **Deployment**: Railway via Docker
- **Styling convention**: Apple Liquid Glass aesthetic on home page cards

## Running Locally

```bash
# Run the Flask backend
cd WSR
pip install -r requirements.txt
python app.py
# Serves on http://localhost:5000

# Run tests
cd WSR
pytest tests/ -v
```

## Key Conventions

- **No build step**: Frontend is plain HTML/CSS/JS served as static files
- **CORS**: Flask adds `Access-Control-Allow-Origin: *` to all responses
- **File size limit**: Flask accepts up to 16MB; API routes enforce 10MB per request
- **Epsilon range**: Vectorization epsilon is validated between 0.0001 and 0.1
- **Ports**: Flask reads `PORT` env var (Railway injects this); defaults to 5000

## Flask Routes (WSR/app.py)

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main interactive background remover UI |
| `/interactive` | GET | Same as `/` |
| `/test` | GET | Test interface page |
| `/process_interactive` | POST | Vectorize an already-edited image |
| `/process_test` | POST | Vectorize with advanced smoothing (test mode) |
| `/process_upscale` | POST | Upscale image with edge preservation |
| `/return-stream.html` | GET | Serve the Return Stream Digitizer static page |

## Return Stream Digitizer (return-stream.html)

Pure client-side tool — no new backend processing. Served as a static file via the Flask route above and copied into the Docker image.

**What it does**: User uploads a PDF or image of a fund fact sheet, crops to the performance chart area, picks the line color, sets axis ranges and date range, and the tool digitizes the performance line into a period-by-period return stream exported as CSV.

**Key implementation details**:
- PDF rendering: PDF.js (CDN) renders pages to a temp canvas at 2× scale
- Three stacked `<canvas>` elements: `chart-canvas` (image), `overlay-canvas` (detected points, pointer-events:none), `interaction-canvas` (mouse events)
- Canvas sizing: all three canvases use CSS `max-width: 100%` / `width: 100% height: 100%` so they scale identically; `eventToImageCoords()` uses `getBoundingClientRect()` for correct pixel mapping at any display size
- Line detection: HSV color space, max-saturation pixel per column (ignores anti-aliased fringe, picks dominant line)
- Chart types supported: Growth of $ (`V_t/V_{t-1} - 1`), Cumulative % (`(1+C_t)/(1+C_{t-1}) - 1`), Period % (direct value/100)
- Date generation: anchors stepping cursor to the 1st of each period (not day-of-month) to prevent month overflow; snaps to end-of-period (last day of month/quarter/Dec 31 for annual); uses local-time `fmtDate()` helper instead of `toISOString()` to avoid UTC day-shift
- Stats output: CAGR, annualized vol, Sharpe, max drawdown
- No smoothing — accuracy is the priority

## Deployment

- Railway auto-deploys from the `main` branch
- Docker builds from `Dockerfile` at repo root
- Health check: `GET /` with 300s timeout
- Restart policy: on_failure, max 10 retries

## DataFinder Agent

AI-powered autonomous web scraping agent. Deployed as a **separate Railway service** from the WSR Flask app.

- **UI**: `data-finder.html` — goal input, format picker (JSON/CSV), SSE streaming log, download button
- **API**: `DataFinderAgent/api.py` — FastAPI app, `POST /scrape` streams per-loop progress events then a final result
- **Run locally**: `cd DataFinderAgent && pip install -e . && uvicorn api:app --port 8000`
- **Config**: Update `API_URL` constant at the top of `data-finder.html` to point to the deployed service URL
- **Env vars needed**: `ANTHROPIC_API_KEY`, `SEARCH_API_KEY`, `SEARCH_PROVIDER` (brave/serpapi/tavily)

See `DataFinderAgent/CLAUDE.md` for full architecture details.

## Adding New Tools

1. Add a new tool card to `index.html` (copy existing card pattern)
2. Add the `data-tool="tool-name"` attribute
3. Add a `case 'tool-name':` in `script.js` `launchTool()` switch
4. Create the tool page (static HTML or new backend service)
5. Add the header bar matching the `the tiny tasks` branding style
