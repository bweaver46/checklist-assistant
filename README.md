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

v0.0.2 — Row counting. Launch Browser opens a Chromium session on
BuySportsCards; Extract Checklist counts the rows currently displayed on the
page.
