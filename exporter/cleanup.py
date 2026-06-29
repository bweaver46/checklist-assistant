"""
Phase 7: cleanup rules.

Insert/Parallel/Sub_Type terminology normalization happens earlier, in
exporter/merge.py (where Insert is computed). What's left here is a
defensive dedupe in case the exact same (parallel, serial) pair shows
up twice for one card.
"""

from __future__ import annotations

from exporter.checklist_template import ChecklistRow


def dedupe_parallels(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        seen = set()
        deduped = []
        for pair in row.parallels:
            if pair not in seen:
                seen.add(pair)
                deduped.append(pair)
        row.parallels = deduped
    return rows


def apply_cleanup(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    return dedupe_parallels(rows)
