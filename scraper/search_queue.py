"""
A staged list of searches to build, test, and run through extraction
one after another (Brandon, 2026-08-10: "lets work on staging
searches. we need a way to test each set, and skip searches that
fail."). Staging + per-entry testing shipped first; Run Queue (running
every passed entry through real extraction, one output file per
search) was added 2026-08-16 - see SearchQueueDialog._on_run_queue in
app/search_queue_dialog.py for the runner itself.

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
RUNNING = "running"
DONE = "done"
ERROR = "error"


@dataclass
class StagedSearch:
    name: str
    fields: dict[str, str] = field(default_factory=dict)
    status: str = UNTESTED
    status_detail: str = ""

    def url(self) -> str:
        return build_search_url(self.fields)

    def output_name(self) -> str:
        """The '[year] [set] [sport]' output name Brandon asked for
        (2026-08-16) for Run Queue's one-file-per-search behavior.
        Falls back to this entry's own name if year/set/sport were all
        left blank (e.g. a keyword-only search), so there's always
        something usable to sanitize into a filename."""
        parts = [
            self.fields.get("year", "").strip(),
            self.fields.get("set", "").strip(),
            self.fields.get("sport", "").strip(),
        ]
        joined = " ".join(p for p in parts if p)
        return joined or self.name

    def display_line(self) -> str:
        icon = {
            "untested": "○", "passed": "✓", "failed": "✗",
            "running": "▶", "done": "✔", "error": "⚠",
        }.get(self.status, "○")
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
