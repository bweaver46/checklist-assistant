"""
Persist the last extraction context so the user doesn't have to retype
everything on every run. Saved to settings/last_run.json (gitignored -
this is local user state, not part of the repo).

The saved dict matches the context dict built by _prompt_for_context in
main_window.py exactly, so it can be handed straight back to the pipeline
or used to pre-fill prompts.
"""

from __future__ import annotations

import json
from pathlib import Path

LAST_RUN_PATH = Path(__file__).resolve().parent / "last_run.json"


def load_last_run() -> dict | None:
    """Return the saved context from the last successful extraction,
    or None if no save file exists yet."""
    if not LAST_RUN_PATH.exists():
        return None
    try:
        with open(LAST_RUN_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # Basic sanity check - must have at least a sport and type.
        if not isinstance(data, dict) or "sport" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_last_run(context: dict) -> None:
    """Save the context dict after a successful extraction. Silently
    swallows errors - a failed save is annoying but not fatal."""
    try:
        with open(LAST_RUN_PATH, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)
    except OSError:
        pass
