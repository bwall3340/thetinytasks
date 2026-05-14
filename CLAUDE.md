# The Tiny Tasks — CLAUDE.md

## 🧠 WHO YOU ARE WORKING WITH

The developer on this project has ADHD. This means:

- They have **strong product vision** but may not enumerate every downstream impact of a feature request.
- They may describe a feature without considering how it touches other modules, surfaces, or data models.
- They need Claude to **fill that gap** — not by making unilateral decisions, but by **surfacing the questions they didn't know to ask**.
- They work best when Claude **thinks ahead, flags conflicts early, and keeps scope explicit**.

This is not a limitation. It is a working style. Adapt to it.

---

## Git Workflow

- Always push changes to the `preprod` branch, never directly to `main`
- `preprod` is merged to `main` via pull request on GitHub
- Railway auto-deploys from `main` — nothing lands in production without a PR

---

## Journey Review Check — Required Before Every Push

Before pushing any feature or fix, walk the complete user journey the change touches. Every step must be fully implemented — no placeholder screens, no dead-end buttons, no tool cards that link to pages that don't exist.

**Rule:** If any step is incomplete, the push is blocked. Finish the journey or explicitly descope the incomplete step with a written explanation.

### How to run a journey check

1. Identify which tool(s) or page(s) the change touches.
2. Walk every step for that tool end-to-end: landing → input → processing → output → error state.
3. Ask: does this step work right now, independently of future work?
4. Flag any step that dead-ends, errors, or depends on unwritten code.
5. Fix or descope before pushing.

### Journey Completeness Rules

- **No orphaned tool cards** — every card on the home page routes to a working tool page.
- **No broken tool flows** — every input path must produce a real output or a clear error message.
- **No silent failures** — every async op (image processing, agent scraping) must surface errors in the UI.
- **No missing data states** — show a meaningful empty state or loading indicator, never a blank area.
- **No dead API calls** — every frontend fetch must point to a live endpoint at the deployed URL.
- **No half-built tools** — a tool is either fully functional or not linked from the home page.

---

## 🔁 RULE 1 — IMPACT SWEEP

Whenever a new feature, enhancement, or change is described, **before writing a single line of code**:

### Step 1: Parse the intent
Restate the feature in one sentence. If ambiguous, ask before proceeding.

### Step 2: Run a module sweep
Walk every module in `## PROJECT MODULES`. For each ask:
> *"Could this feature affect [Module]? Even indirectly — data shape, UI state, permissions, navigation, API surface, or user expectation?"*

Surface any **yes or maybe** with a one-line explanation and ask how to handle it. **Do not skip this sweep, even for small features.**

### Step 3: Confirm scope before building

```
FEATURE: [name]
DIRECTLY AFFECTS: [list]
POTENTIALLY AFFECTS: [list]
OUT OF SCOPE: [list]
OPEN QUESTIONS: [list]
```

Do not proceed until scope is confirmed.

---

## 📐 RULE 2 — COMPLETE PATH REQUIRED

Every feature must have a defined start, finish, and clear path between them before implementation. Before writing code:

```
PATH: [Feature Name]
──────────────────────────────────────────
ENTRY:      [trigger or user action]
DATA:       [inputs / outputs / file types]
LOGIC:      [key steps in plain language]
UI:         [surfaces, states, transitions]
EXIT:       [outcome / next state]
EDGE CASES: [failure modes, empty states]
──────────────────────────────────────────
READY TO BUILD: yes / pending [question]
```

If any row is undefined, ask before building. Partial paths produce broken tools.

---

## 🐛 RULE 3 — ERROR LOG PROTOCOL

When an error log, stack trace, or bug is reported:

1. **Diagnose root cause** — identify *why* it occurred, not just where.
2. **Fix the instance** — targeted fix for the specific error.
3. **Write a prevention rule** — add to `## LEARNED RULES`:

```
[DATE] — [Error Class]: [What caused it] → [Prevention rule going forward]
```

Every bug becomes a permanent guardrail.

---

## 🎨 RULE 4 — DESIGN ALIGNMENT

**Before planning or building any new feature, UI change, or visual enhancement**, open `design.md` and verify the proposed work aligns with the design system defined there.

### Checklist before any UI work

1. **Color** — does it use the defined palette (`--cream`, `--olive`, `--terra`, `--stone`, `--ink`, `--border`)? No neon, no pure black/white.
2. **Typography** — headings use the designated serif; body uses the designated sans-serif.
3. **Tone** — does the copy feel calm, understated, and quietly confident? No buzzwords.
4. **Motion** — animations are slow, smooth, subtle. No flashy transitions.
5. **Aesthetic** — does it feel like a boutique Italian workshop, not a Silicon Valley startup?

### When in doubt

Flag the conflict explicitly before building:

```
DESIGN CONFLICT: [what you're about to build]
CONFLICTS WITH: [specific design.md rule or section]
PROPOSED RESOLUTION: [how to align it]
```

Do not proceed until resolved.

---

## Project Overview

The Tiny Tasks is a multi-tool web application deployed on Railway. The home page is a static frontend; individual tools are either pure client-side HTML/JS or served by a Python Flask backend. Each tool is a self-contained utility — image processing, AI-powered data scraping, chart digitization, and more.

---

## Architecture

```
Railway (Docker — Flask app)
├── Home page (static HTML/CSS/JS)
├── Tool pages (static HTML or Flask-served)
├── Flask API routes (WSR/)    ←→  Image processing (OpenCV, Pillow)
         ↕
    (no shared DB — stateless per-request)

Railway (separate service — DataFinderAgent)
├── FastAPI SSE wrapper (api.py)
├── Agent orchestrator + tools
         ↕
    Anthropic Claude API + Search API
```

- **Frontend**: Vanilla HTML, CSS, JavaScript — no framework, no build step
- **Backend**: Python 3.11, Flask 3.0, gunicorn — served via Docker on Railway
- **Image Processing**: OpenCV, Pillow, scikit-image, scipy, numpy
- **AI Agent**: Anthropic Claude API via the DataFinderAgent FastAPI service (separate Railway deployment)
- **Deployment**: Railway auto-deploys `main` via Docker

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vanilla HTML / CSS / JavaScript |
| Backend | Python 3.11, Flask 3.0, gunicorn |
| Image processing | OpenCV, Pillow, scikit-image, scipy, numpy |
| AI agent | Anthropic SDK (`anthropic`), FastAPI, Playwright |
| Deployment | Railway (Docker) |
| Styling convention | Apple Liquid Glass aesthetic on home page cards |

---

## Brand

- **Product**: The Tiny Tasks
- **Tone**: Minimal, utilitarian, quietly delightful — tools that just work
- **Styling**: Apple Liquid Glass aesthetic on home page cards; individual tools match the header bar pattern
- **Full design system**: See `design.md` — all UI work must align with it (see Rule 4)

---

## Repository Structure

```
thetinytasks/
├── index.html              # Home page with tool cards
├── styles.css              # Home page styles (Apple Liquid Glass aesthetic)
├── script.js               # Home page navigation logic
├── data-finder.html        # DataFinder Agent tool UI (SSE streaming)
├── background-remover.html # Background Remover Pro tool UI
├── return-stream.html      # Return Stream Digitizer (pure client-side)
├── Sankey/                 # Sankey Chart tool (pure client-side HTML)
├── WhiteBackgroundRemover/ # Simple client-side white bg remover
├── WSR/                    # Flask backend (vectorizer / background remover)
│   ├── app.py              # Flask app, all routes defined here
│   ├── vectorizer_engine.py
│   ├── detailed_vectorizer.py
│   ├── extreme_vectorizer.py
│   ├── test_vectorizer.py  # AdvancedTestVectorizer class (NOT a test file)
│   ├── logo_upscaler.py
│   ├── requirements.txt
│   └── tests/
│       ├── conftest.py
│       └── test_app.py
├── DataFinderAgent/        # AI web scraping agent (separate Railway service)
│   ├── CLAUDE.md           # Full architecture spec for the agent
│   ├── api.py              # FastAPI SSE wrapper — POST /scrape
│   ├── agent/              # Orchestrator, tools, strategy engine, output formatter
│   ├── cli/                # Typer CLI entry point
│   └── pyproject.toml
├── Dockerfile              # Builds WSR/ Flask app
└── railway.toml            # Railway deployment config
```

---

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

---

## 🗂️ PROJECT MODULES

Used by the Impact Sweep (Rule 1). Update this list when modules are added.

- [ ] Home Page / Tool Cards (`index.html`, `styles.css`, `script.js`)
- [ ] DataFinder Agent UI (`data-finder.html`)
- [ ] DataFinder Agent Backend (`DataFinderAgent/` — FastAPI + agent orchestrator)
- [ ] Background Remover Pro UI (`background-remover.html`)
- [ ] Flask Image Processing Backend (`WSR/app.py` + engine files)
- [ ] Return Stream Digitizer (`return-stream.html` — pure client-side)
- [ ] Sankey Chart Tool (`Sankey/`)
- [ ] White Background Remover (`WhiteBackgroundRemover/`)
- [ ] Docker / Deployment (`Dockerfile`, `railway.toml`)

---

## Coding Conventions

- **No build step** — frontend is plain HTML/CSS/JS served as static files
- **CORS** — Flask adds `Access-Control-Allow-Origin: *` to all responses
- **File size limit** — Flask accepts up to 16MB; API routes enforce 10MB per request
- **Epsilon range** — vectorization epsilon validated between 0.0001 and 0.1
- **Ports** — Flask reads `PORT` env var (Railway injects this); defaults to 5000
- **Tool page header** — every tool page uses the standard `the tiny tasks` header bar pattern
- **New tool card** — new tools follow the existing card pattern in `index.html` with a matching `case` in `script.js`

### AI calls — DataFinderAgent only, never from Flask routes

All Anthropic API calls go through `DataFinderAgent/agent/`. The WSR Flask app never calls the Anthropic SDK — it is a pure image-processing backend.

### Anthropic API — retry on transient errors, never swallow them

```python
import anthropic
import time

def call_with_retry(fn, attempts=3):
    for i in range(attempts):
        try:
            return fn()
        except anthropic.APIStatusError as e:
            if e.status_code in (529,) or e.status_code >= 500:
                if i < attempts - 1:
                    time.sleep(2 ** i)
                else:
                    raise
            else:
                raise  # auth errors, validation errors — don't retry
```

- Use `claude-sonnet-4-6` for standard agent runs
- Always set `max_tokens` explicitly

### Flask — validate inputs at the route boundary

Validate file type, size, and parameters at the top of each route before passing to processing functions. Never pass raw user input into shell commands or `eval()`.

### Return Stream Digitizer — canvas sizing invariant

All three stacked canvases (`chart-canvas`, `overlay-canvas`, `interaction-canvas`) must use identical CSS sizing. Always use `getBoundingClientRect()` via `eventToImageCoords()` for pixel mapping — never read `offsetX`/`offsetY` directly.

### Adding a new tool — required checklist

1. Add a tool card to `index.html` (copy existing card pattern)
2. Add `data-tool="tool-name"` attribute to the card
3. Add `case 'tool-name':` in `script.js` `launchTool()` switch
4. Create the tool page with the standard header bar
5. If a new Flask route is needed, add it to `WSR/app.py` and update the Flask Routes table above
6. Run a journey check before pushing

---

## Running Locally

```bash
# Flask backend
cd WSR
pip install -r requirements.txt
python app.py
# Serves on http://localhost:5000

# DataFinder Agent
cd DataFinderAgent
pip install -e .
uvicorn api:app --port 8000

# Run tests
cd WSR
pytest tests/ -v
```

---

## 🤝 Collaboration Norms

- Ask questions **before building**, not after. Group related questions together.
- If a question has a reasonable default, state it and proceed unless objected to.
- **Proceed** on implementation details and code patterns that don't affect product behavior.
- **Pause** on anything that changes data shape, user-facing behavior, tool routing, or scope.
- Every function does one thing. Every new file has a clear module owner.
- No magic strings. No hardcoded values that might change.
- When a pattern is established for the first time, note it so it becomes the template.
- Use the same terminology everywhere — match the developer's words exactly.

---

## Environment Variables

```
# DataFinderAgent
ANTHROPIC_API_KEY=     # Anthropic API key
SEARCH_API_KEY=        # Key for the configured search provider
SEARCH_PROVIDER=       # brave | serpapi | tavily

# Flask / WSR (Railway injects PORT automatically)
PORT=5000              # Overridden by Railway at deploy time
```

---

## 📋 Feature Log

| Feature | Status | Modules Affected | Notes |
|---------|--------|-----------------|-------|
| (none yet) | — | — | — |

Status: `scoping` → `in progress` → `needs review` → `done`

---

## 🔒 Learned Rules

**2026-05-06 — Schema Migration**: Added columns to an existing table by only updating the SQLAlchemy model. `db.create_all()` creates missing tables but never alters existing ones, so the new columns were absent in production → `UndefinedColumn` crash on first request. **Prevention rule**: Any time a column is added to an existing model, also append an `ALTER TABLE … ADD COLUMN` statement to the `_migrations` list in `WSR/app.py`. The try/except wrapper makes it safe to re-run (silently ignored if column already exists).

---

This file is a living document. When a module is added, update `## PROJECT MODULES`. When a naming convention is established, add it to `## Collaboration Norms`. When a bug produces a prevention rule, add it to `## Learned Rules`. Prune stale entries periodically.
