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

v0.7.0 — **First successful live test passed**: a real extraction
against Mike Trout / 2026 Bowman pulled 564 rows across multiple pages
and merged them down to 68 unique cards with no errors.

Fixed from that test: Type prompt removed (hardcoded to "Sports" since
BSC is sports-only), Section prompt reworded for clarity, and CSV output
paths are now reported as full absolute paths so it's obvious where the
files landed (they were always being written correctly - just not
obviously located).

See `docs/VISION.md` for the full open-questions list (the "Refractor
in card data" edge cases, continuation-numbering scenarios as more turn
up, etc.).

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
