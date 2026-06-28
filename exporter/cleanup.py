"""
Phase 7: cleanup rules.

Implemented:
    - dedupe_occurrences: defensive dedupe in case the exact same
      occurrence shows up twice (e.g. the same card appearing on two
      different pages due to a mid-extraction re-sort).
    - standardize_insert_names: punctuation/spacing normalization on
      insert/parallel names per Brandon's examples (2026-06-28):
        - "Black Wave" vs "Black-Wave" -> hyphens treated as spaces,
          collapsed to one consistent form.
        - Extra/irregular whitespace collapsed and trimmed.

NOT implemented yet - need more specifics before this is safe to
automate:
    - "Blue Mojo" vs "Blue Mojo Refractor" (when appropriate) - dropping
      a trailing descriptor word like "Refractor" is sometimes right and
      sometimes not. Tell me the actual rule (e.g. "always drop trailing
      'Refractor' when there's no other parallel-color word" or
      whatever the real logic is) and I'll add it as its own function.
"""

import re

from exporter.checklist_template import ChecklistRow

WHITESPACE_PATTERN = re.compile(r"\s+")


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


def normalize_insert_name(name: str) -> str:
    """'Black-Wave' -> 'Black Wave'. Collapses/trims whitespace too."""
    if not name:
        return name
    normalized = name.replace("-", " ")
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def standardize_insert_names(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        row.occurrences = [
            (normalize_insert_name(insert), sub_type, serial)
            for (insert, sub_type, serial) in row.occurrences
        ]
    return rows


def apply_cleanup(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    rows = standardize_insert_names(rows)
    rows = dedupe_occurrences(rows)
    return rows
