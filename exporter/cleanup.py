"""
Phase 7: cleanup rules.

Most of "remove redundant Base" now happens earlier in convert.py (a
plain Base row never becomes an occurrence at all). What's left here is
a defensive dedupe in case the same exact occurrence shows up twice
(e.g. the same card appearing on two different pages due to a
mid-extraction re-sort).

NOT implemented, because they depend on rules only Brandon has:
    - continuation numbering
    - standardize names

Tell me the rule and I'll add it as its own function here.
"""

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
    rows = dedupe_occurrences(rows)
    return rows
