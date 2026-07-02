"""
Team Cache

Persists the player-name -> team lookup across multiple extraction runs
so BSC's "Add" page only gets visited once per unique player name, ever,
not once per player per run.

Stored alongside the accumulator in settings/team_cache.json (gitignored).
Cleared at the same time as the accumulator - they belong to the same
search session.
"""

from __future__ import annotations

import json
from pathlib import Path

TEAM_CACHE_PATH = Path(__file__).resolve().parent / "team_cache.json"


def load_team_cache() -> dict[str, str]:
    """Return the saved player->team mapping, or {} if none."""
    if not TEAM_CACHE_PATH.exists():
        return {}
    try:
        with open(TEAM_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_team_cache(cache: dict[str, str]) -> None:
    """Overwrite the saved cache with the current contents."""
    try:
        with open(TEAM_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass


def clear_team_cache() -> None:
    """Delete the team cache file."""
    try:
        TEAM_CACHE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
