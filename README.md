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

v0.3.0 — Full Phase 1-8 pipeline (read all pages → raw CSV → checklist
format → merge parallels → cleanup → final CSV) is wired and unit-tested
against fake data. **Not yet validated against the live BuySportsCards
site** — `settings/selectors.py` and `exporter/convert.py`'s field
mapping are placeholder guesses until confirmed against the real DOM.
See `docs/VISION.md` "Blocked On" for the exact next step.

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
