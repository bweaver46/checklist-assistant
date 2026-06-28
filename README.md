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

### Easier launch (Mac)

After the one-time setup above, double-click **`Launch Checklist Assistant.command`**
in Finder to start the app without typing anything into Terminal. To put
it somewhere convenient: right-click the file → Make Alias, then drag
that alias to your Desktop or Dock.

Window positions (where the app window and the browser window open on
screen) are set in `settings/window_layout.py` if you want to move them.

## Status

v0.8.0 — Fixes from reviewing the actual 564-row live extraction output:
`set` strips the year (already has its own column), card-number
prefixes like "T91-" or "BA-" now move to the front of insert (applied
after hyphen-normalization so the prefix's own hyphen survives), and an
optional "Primary Player" prompt splits a player's name out of a messy
multi-name Name field, moving the rest into sub_type.

See `docs/VISION.md` for the full open-questions list.

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
