# The Tiny Tasks - CLAUDE.md

## Project Overview

A multi-tool web application deployed on Railway. The home page is a static frontend; individual tools are either pure client-side HTML/JS or served by a Python Flask backend.

## Repository Structure

```
thetinytasks/
├── index.html              # Home page with tool cards
├── styles.css              # Home page styles (Apple Liquid Glass aesthetic)
├── script.js               # Home page navigation logic
├── background-remover.html # Background Remover Pro tool (links to WSR backend)
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

## Deployment

- Railway auto-deploys from the `main` branch
- Docker builds from `Dockerfile` at repo root
- Health check: `GET /` with 300s timeout
- Restart policy: on_failure, max 10 retries

## Adding New Tools

1. Add a new tool card to `index.html` (copy existing card pattern)
2. Add the `data-tool="tool-name"` attribute
3. Add a `case 'tool-name':` in `script.js` `launchTool()` switch
4. Create the tool page (static HTML or new backend service)
5. Add the header bar matching the `the tiny tasks` branding style
