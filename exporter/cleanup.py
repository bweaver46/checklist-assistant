"""
Phase 7: cleanup rules.

Implemented:
    - dedupe_occurrences: defensive dedupe in case the exact same
      occurrence shows up twice (e.g. the same card appearing on two
      different pages due to a mid-extraction re-sort).
    - standardize_insert_names: punctuation/spacing + terminology
      normalization on insert/parallel names per Brandon's examples
      (2026-06-28):
        - "Black Wave" vs "Black-Wave" -> hyphens treated as spaces.
        - "Blue Mojo" vs "Blue Mojo Refractor" -> a trailing
          "Refractor"/"Refractors" is redundant and gets dropped.
        - "Prizm" vs "Prizms", "Refractor" vs "Refractors" -> any
          remaining (non-trailing) occurrence gets normalized to the
          singular form for consistency.
        - Extra/irregular whitespace collapsed and trimmed.

NOT implemented yet - need more specifics before this is safe to
automate:
    - continuation numbering's interaction with non-Prospects-style
      subsections, if any exist beyond what's already handled via the
      Section context field.
"""

from __future__ import annotations

import re

from exporter.checklist_template import ChecklistRow

WHITESPACE_PATTERN = re.compile(r"\s+")
TRAILING_REFRACTOR_PATTERN = re.compile(r"\s+Refractors?\s*$", re.IGNORECASE)
PLURAL_TERM_PATTERN = re.compile(r"\b(Prizms?|Refractors?)\b", re.IGNORECASE)


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


def _normalize_plural_term(match: "re.Match") -> str:
    word = match.group(0).lower()
    return "Prizm" if word.startswith("prizm") else "Refractor"


def normalize_insert_name(name: str) -> str:
    """'Black-Wave' -> 'Black Wave'. 'Blue Mojo Refractor' -> 'Blue Mojo'.
    'Prizms'/'Refractors' -> 'Prizm'/'Refractor' wherever they remain.
    Collapses/trims whitespace throughout."""
    if not name:
        return name

    normalized = name.replace("-", " ")
    normalized = TRAILING_REFRACTOR_PATTERN.sub("", normalized)
    normalized = PLURAL_TERM_PATTERN.sub(_normalize_plural_term, normalized)
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
