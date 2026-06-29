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

v0.9.0 — Major data model change to match `sets-template-2.csv` exactly:
Insert and Sub_Type are now scalar (one value per card), computed from
what's common across all of a card's print versions. Only
Parallel/Serial repeat. The "drop redundant Refractor" rule was removed
(it conflicted with real data - Refractors now singularize instead of
disappearing). Brand/Set split changed to "brand = first word after
year, set = everything else." Extraction prompts now wrap properly
instead of stretching across the screen.

See `docs/VISION.md` for the full open-questions list.

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
