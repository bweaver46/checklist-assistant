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

v0.6.0 — Section context (for continuation-numbering subsections like
"Prospects" - set/card_number never renumbered, section name goes into
sub_type instead) and insert-name punctuation standardization
(hyphen/space normalization) added per Brandon's direction. App now
prompts for Sport/Type/Team/Section once per extraction run.

**Not yet run end-to-end inside the actual desktop app against a live
page** — that's the next step.

See `docs/VISION.md` "Open Questions" for what's still unresolved (the
"Blue Mojo" vs "Blue Mojo Refractor" rule, and whatever else turns up
once this runs against real data).

Run tests with: `PYTHONPATH=. python3 tests/test_exporter_pipeline.py`
