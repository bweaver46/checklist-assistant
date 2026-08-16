"""
Persist the last-used "Build a Search" field values so adding another
staged search doesn't require retyping everything when only one field
actually changes (Brandon, 2026-08-16: "when adding a search it should
maintain all of the fields from the last time it was filled out so that
if only one field changes I don't have to fill it out again"). Saved to
settings/last_search.json (gitignored - local user state, same spirit
as settings/last_run.py's last_run.json, just for the search-builder
form instead of the full extraction context).
"""

from __future__ import annotations

import json
from pathlib import Path

LAST_SEARCH_PATH = Path(__file__).resolve().parent / "last_search.json"


def load_last_search() -> dict[str, str]:
    """Return the saved field values from the last search built, or an
    empty dict if there's no save file yet (so callers can always do
    `defaults.get(key, "")` without a None check)."""
    if not LAST_SEARCH_PATH.exists():
        return {}
    try:
        with open(LAST_SEARCH_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def save_last_search(fields: dict[str, str]) -> None:
    """Save the field values after a search is successfully built.
    Silently swallows errors - a failed save is annoying but not fatal,
    same as save_last_run."""
    try:
        with open(LAST_SEARCH_PATH, "w", encoding="utf-8") as f:
            json.dump(fields, f, indent=2)
    except OSError:
        pass
