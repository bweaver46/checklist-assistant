"""
Phase 7: cleanup rules.

Insert-name punctuation/terminology normalization (hyphens, redundant
Refractor, Prizm/Refractor plurals) now happens earlier, in
exporter/convert.py - it has to run BEFORE the card-number prefix gets
prepended to insert text, or the hyphen-normalization rule would
incorrectly strip the hyphen out of prefixes like "T91-". See
convert.normalize_insert_name for the actual logic.

What's left here:
    - dedupe_occurrences: defensive dedupe in case the exact same
      occurrence shows up twice (e.g. the same card appearing on two
      different pages due to a mid-extraction re-sort, or two raw rows
      that only differed by now-normalized punctuation).
"""

from __future__ import annotations

from exporter.checklist_template import ChecklistRow


def dedupe_occurrences(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        seen = set()
        deduped = []
        for occurrence in row.occurrences:
            if occurrence not in seen:
                seen.add(occurrence)
                deduped.append(occurrence)
        row.occurrences = deduped
    return rows


def apply_cleanup(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    return dedupe_occurrences(rows)
