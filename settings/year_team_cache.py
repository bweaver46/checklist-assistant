"""
Year Team Cache

Persists the (player, year) -> team check-in state across extraction
runs, for Player-mode team fetching (see TEAM_RECHECK_INTERVAL in
settings/extraction_limits.py and BrowserManager.read_all_rows'
sample_team_by_year logic).

Each value under a "player|year" key is one of:
    - {"team": <str>, "count_since_check": <int>} - the currently
      assumed team for this player/year, and how many non-lettered rows
      have been read since it was last confirmed. Once
      count_since_check reaches TEAM_RECHECK_INTERVAL, the next row
      triggers a real fetch to confirm the assumption still holds
      (resetting count_since_check to 0) or discovers it doesn't.
    - the literal string "MIXED" - a recheck disagreed with the assumed
      team (a trade happened this year); every remaining row for this
      player/year gets fetched individually from here on, no more
      caching for this key.

Stored alongside the accumulator and team_cache in
settings/year_team_cache.json (gitignored). Cleared at the same time as
the accumulator and team_cache - they all belong to the same search
session.
"""

from __future__ import annotations

import json
from pathlib import Path

YEAR_TEAM_CACHE_PATH = Path(__file__).resolve().parent / "year_team_cache.json"

MIXED = "MIXED"


def load_year_team_cache() -> dict[str, dict | str]:
    """Return the saved (player, year) check-in cache, or {} if none."""
    if not YEAR_TEAM_CACHE_PATH.exists():
        return {}
    try:
        with open(YEAR_TEAM_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_year_team_cache(cache: dict[str, dict | str]) -> None:
    """Overwrite the saved cache with the current contents."""
    try:
        with open(YEAR_TEAM_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass


def clear_year_team_cache() -> None:
    """Delete the year team cache file."""
    try:
        YEAR_TEAM_CACHE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
