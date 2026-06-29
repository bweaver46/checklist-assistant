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

v0.10.0 — Added optional per-card Team fetching for full-set pulls
spanning multiple teams. Team isn't shown in BSC's results table at
all - only on the detail page reached by clicking "Add" - so this is
an explicit opt-in choice (it's meaningfully slower: one extra page
visit per card) with a Yes/No prompt before each extraction, not a
silent default. Confirmed safe to navigate into and back out of
(doesn't submit or create a listing) - not yet confirmed safe at very
high volume against BSC's systems, so test on a moderate batch first.

See `docs/VISION.md` for the full open-questions list.

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
