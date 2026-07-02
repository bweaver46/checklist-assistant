"""
Accumulator

Persists raw CardRecord rows across multiple extraction runs so the
final CSV can be built from a combination of page-range batches.

Workflow:
    Run 1: pages 1-100   -> appends  ~5,000 rows  -> writes CSV from   ~5,000
    Run 2: pages 101-200 -> appends  ~5,000 rows  -> writes CSV from  ~10,000
    Run 3: pages 201-300 -> appends  ~5,000 rows  -> writes CSV from  ~15,000
    Clear                -> resets to 0 rows

Storage: settings/accumulator.json (gitignored, local user state).
Format:  JSON list of dicts, one dict per CardRecord row.
"""

from __future__ import annotations

import json
from pathlib import Path

from scraper.card_record import CardRecord

ACCUMULATOR_PATH = Path(__file__).resolve().parent / "accumulator.json"


def load_accumulated() -> list[CardRecord]:
    """Return all rows saved from previous runs, or [] if none."""
    if not ACCUMULATOR_PATH.exists():
        return []
    try:
        with open(ACCUMULATOR_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [CardRecord(**row) for row in data]
    except (json.JSONDecodeError, OSError, TypeError):
        return []


def save_accumulated(records: list[CardRecord]) -> None:
    """Overwrite the accumulator with the given list (pass the full
    combined list, not just the new rows)."""
    try:
        with open(ACCUMULATOR_PATH, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, indent=2)
    except OSError:
        pass


def clear_accumulated() -> None:
    """Delete the accumulator file, resetting to zero rows."""
    try:
        ACCUMULATOR_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def accumulated_count() -> int:
    """Return the number of rows saved so far without loading everything."""
    records = load_accumulated()
    return len(records)
