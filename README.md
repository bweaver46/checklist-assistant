# Checklist Assistant

Desktop app that automates building trading card checklist CSVs from online
sources. See [docs/VISION.md](docs/VISION.md) for the full project vision,
architecture, and roadmap.

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Status

v0.4.0 — Selectors and field mapping confirmed against the live,
logged-in BuySportsCards table (see `docs/VISION.md`). Full Phase 1-8
pipeline (read all pages → raw CSV → checklist format → merge parallels
→ cleanup → final CSV) is wired and tested against fake data shaped
exactly like the real table. **Not yet run end-to-end inside the actual
desktop app against a live page** — that's the next step.

See `docs/VISION.md` "Open Questions" for what's still unresolved
(autograph representation, sport/year/brand context, naming rules).

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
