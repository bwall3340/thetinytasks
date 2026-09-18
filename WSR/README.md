# WSR — Flask backend for The Tiny Tasks

Image processing for the Background Remover Pro tool, plus the Market Outlook,
Meal Planner and Site Admin modules. Deployed on Railway via the repo-root
`Dockerfile`; `app.py` is the only place routes are defined.

The tool UI itself is `background-remover.html` at the repo root — this package
serves it and does the processing. There is no separate vectorizer page.

## Running locally

```bash
cd WSR
pip install -r requirements.txt
python app.py          # http://localhost:5000
```

`SITE_DIR` falls back to the repo root when `WSR/site/` is absent, so the home
page and the tool pages work from a plain checkout. In the Docker image the
root-level site files are copied to `/app/site` and that is used instead.

## Tests

```bash
cd WSR
pytest tests/ -v
```

- `test_app.py` — route and processing-endpoint behaviour
- `test_site_admin.py` — image slots and shared admin auth
- `test_live_surface.py` — what the deployed site depends on: every `fetch()`
  resolves to a real route, every linked page is served, every tool card routes
  somewhere, the Dockerfile copies what the routes serve, and nothing
  server-side is orphaned. Run this before deleting anything.

## Processing endpoints

| Endpoint | Engine | Used by |
|----------|--------|---------|
| `POST /process_interactive` | `detailed_vectorizer` / `extreme_vectorizer` (by epsilon) | Interactive mode |
| `POST /process_vtracer` | `vtracer_engine` — colour vectorization | Vectorizer mode |
| `POST /process_upscale` | `logo_upscaler` | Upscaler mode |
| `POST /process_test` | `test_vectorizer` — adds `smoothing_level` | **nothing** — see below |

Every endpoint validates file type, size (10MB) and parameters at the route
boundary before touching the processing code.

### `/process_test` has no caller

`test_vectorizer.py` (`AdvancedTestVectorizer`, ~2,100 lines) implements edge
smoothing that no UI exposes. It is kept because the capability is real and
unique, not because anything uses it. Either wire `smoothing_level` into the
Vectorizer mode's detail control, or delete the endpoint and the module — but
decide, rather than leaving it to rot a second time.

## Engines

| Module | Role |
|--------|------|
| `detailed_vectorizer.py` | High-quality contour vectorization with curves |
| `extreme_vectorizer.py` | Pixel-perfect vectorization at epsilon ≤ 0.0001 |
| `vtracer_engine.py` | Colour vectorization via the `vtracer` crate |
| `logo_upscaler.py` | Upscaling, edge enhancement, background flattening |
| `test_vectorizer.py` | Edge-smoothing vectorizer — not a test file |

## Epsilon

Vectorization detail, validated between 0.0001 and 0.1. Lower means more
contours and a larger SVG.
