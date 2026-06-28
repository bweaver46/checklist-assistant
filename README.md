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

v0.5.0 — Field mapping rules applied per Brandon's direction: insert,
sub_type, and serial are now per-occurrence (insert_1/sub_type_1/serial_1,
insert_2/sub_type_2/serial_2, ...), year/brand parsed from the Set
string, plain Base rows dropped, Autograph dedup rule applied, and the
app now prompts for Sport/Type once per extraction run.

**Not yet run end-to-end inside the actual desktop app against a live
page** — that's the next step.

See `docs/VISION.md` "Open Questions" for what's still unresolved (team
source, naming/continuation rules).

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
