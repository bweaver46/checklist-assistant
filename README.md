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

v0.9.2 — Added more brand/set exceptions (President's Choice, Lauran
Taylor, Upper Deck, UD->Upper Deck), fixed a gap where exception
matches dropped trailing words (e.g. "UD Series 1" was losing "Series
1"), sorted the final CSV by brand, and raised the page extraction
safety cap from 200 to 2000 (a large search was hitting the old limit
and stopping early).

See `docs/VISION.md` for the full open-questions list.

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
