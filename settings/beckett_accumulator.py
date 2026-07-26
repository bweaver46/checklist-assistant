"""
Beckett Accumulator

Persists raw Beckett-parsed row dicts (plus the export name they're
being written under) across multiple Extract Beckett Checklist runs.

Confirmed 2026-07-26 (Brandon): a lot of Beckett products are split
across several articles that all build on the SAME year/brand/set -
e.g. "2026 Topps Series 1 Baseball" (the base release), "...Celebration
Mega Box", "...All-Star Game Mega Box" - each adding its own exclusive
inserts/parallels on top of the same base checklist and card
numbering. He wants those combined into one CSV, the same way BSC's
page-range chunks combine via settings/accumulator.py - NOT mixed
across genuinely different sets (that's on him to keep straight by
typing the same Product/Sport each time, and pressing Clear
Accumulated Data before starting an actually different one).

output_name is captured on the FIRST pull of a session (via
resolve_unique_output_name) and then reused for every subsequent pull
in that same session, so the file doesn't get a new "(2)"-style name
each time - only the row content grows.

Storage: settings/beckett_accumulator.json (gitignored, local state).
Cleared by the same "Clear Accumulated Data" button as the BSC
accumulator.
"""

from __future__ import annotations

import json
from pathlib import Path

BECKETT_ACCUMULATOR_PATH = Path(__file__).resolve().parent / "beckett_accumulator.json"


def load_beckett_accumulated() -> tuple[list[dict], str]:
    """Return (rows, output_name) from previous runs, or ([], "") if none."""
    if not BECKETT_ACCUMULATOR_PATH.exists():
        return [], ""
    try:
        with open(BECKETT_ACCUMULATOR_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return [], ""
        rows = data.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        for row in rows:
            if isinstance(row, dict) and "parallels" in row:
                row["parallels"] = [tuple(p) for p in row["parallels"]]
        output_name = data.get("output_name", "")
        return rows, output_name if isinstance(output_name, str) else ""
    except (json.JSONDecodeError, OSError, TypeError):
        return [], ""


def save_beckett_accumulated(rows: list[dict], output_name: str) -> None:
    """Overwrite the accumulator with the given full combined row list
    and output name (pass the full list, not just the new rows)."""
    try:
        with open(BECKETT_ACCUMULATOR_PATH, "w", encoding="utf-8") as f:
            json.dump({"output_name": output_name, "rows": rows}, f, indent=2)
    except OSError:
        pass


def clear_beckett_accumulated() -> None:
    """Delete the Beckett accumulator file, resetting to zero rows."""
    try:
        BECKETT_ACCUMULATOR_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def beckett_accumulated_count() -> int:
    """Return the number of rows saved so far without needing the caller
    to unpack the tuple themselves."""
    rows, _ = load_beckett_accumulated()
    return len(rows)
