"""
A staged list of searches to build, test, and (eventually) run through
extraction one after another - the first piece of the queue feature
Brandon asked for (2026-08-10): "lets work on staging searches. we
need a way to test each set, and skip searches that fail."

This module is intentionally scoped to just staging + testing for now,
matching how Brandon asked to build this up: get search-URL building
and navigation solid on its own first (scraper/search_url.py, already
shipped), then staging + per-entry testing (this module), and only
after that actually wire up "run every passed entry through extraction
automatically" - see StagedSearch.status for where that hook goes.

Persisted to settings/staged_searches.json so a staged list survives
an app restart, same spirit as the other settings/*.csv files, just
JSON since each entry is a small structured record rather than one
flat row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from scraper.search_url import build_search_url

QUEUE_PATH = Path(__file__).resolve().parent.parent / "settings" / "staged_searches.json"

UNTESTED = "untested"
PASSED = "passed"
FAILED = "failed"


@dataclass
class StagedSearch:
    name: str
    fields: dict[str, str] = field(default_factory=dict)
    status: str = UNTESTED
    status_detail: str = ""

    def url(self) -> str:
        return build_search_url(self.fields)

    def display_line(self) -> str:
        icon = {"untested": "○", "passed": "✓", "failed": "✗"}.get(self.status, "○")
        detail = f" — {self.status_detail}" if self.status_detail else ""
        return f"{icon} {self.name}{detail}"


def load_queue() -> list[StagedSearch]:
    if not QUEUE_PATH.exists():
        return []
    try:
        raw = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [StagedSearch(**entry) for entry in raw]


def save_queue(entries: list[StagedSearch]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps([asdict(e) for e in entries], indent=2),
        encoding="utf-8",
    )


def passed_entries(entries: list[StagedSearch]) -> list[StagedSearch]:
    """The entries a later queue-runner should actually pull - passed
    ones only. Untested entries are excluded too, not just failed ones:
    an entry that's never been checked shouldn't be assumed good."""
    return [e for e in entries if e.status == PASSED]
