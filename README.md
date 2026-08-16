# Checklist Assistant

Desktop app that automates building trading card checklist CSVs from online
sources. See [docs/VISION.md](docs/VISION.md) for the full project vision,
architecture, and roadmap.

## Quick Start

### Mac / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

If `python` isn't recognized, you likely need the "Add python.exe to PATH"
checkbox during the Python installer, or use `py` instead of `python` for
the first two commands.

## Easier launch (after the one-time setup above)

**Mac:** double-click **`Launch Checklist Assistant.command`** in Finder.
To put it somewhere convenient: right-click the file → Make Alias, then
drag that alias to your Desktop or Dock.

**Windows:** double-click **`Launch Checklist Assistant.bat`** in File
Explorer. To put it somewhere convenient: right-click the file → Show
more options → Send to → Desktop (create shortcut).

Window positions (where the app window and the browser window open on
screen) are set in `settings/window_layout.py` if you want to move them.

## Status

v0.10.1 — Added a per-player Team cache: "Add" now only gets clicked
once per distinct player name for the whole extraction run, not once
per row - most rows in any set are parallels of the same player, so
this is a large speedup for full-set pulls with Team fetching enabled.
Also added `docs/HANDOFF_1.md`, a comprehensive project handoff.

See `docs/VISION.md` for the full open-questions list, and
`docs/HANDOFF_1.md` for full project orientation.

Run tests with:
```
PYTHONPATH=. python3 tests/test_exporter_pipeline.py
PYTHONPATH=. python3 tests/test_browser_manager.py
```
