"""
Phase 7: cleanup rules.

*** Starting point only - NOT validated against your real checklist conventions. ***

Implemented here:
    - remove_redundant_base: drop a bare "Base" parallel entry (a card with
      only a Base printing shouldn't show parallel_1=Base, it should show
      no parallels at all)
    - normalize_serials: strip leading zeros from serial numbers
    - dedupe_parallels: drop exact duplicate (name, serial) pairs on the
      same row

NOT implemented, because they depend on rules only you have:
    - continuation numbering (what counts as a "continuation" of a set,
      and how it should be numbered)
    - standardize names (what your canonical name strings should look
      like, e.g. abbreviations, casing, punctuation conventions)

Tell me the rule and I'll add it as its own function here.
"""

from exporter.checklist_template import ChecklistRow


def remove_redundant_base(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        row.parallels = [
            (name, serial) for (name, serial) in row.parallels
            if name.strip().lower() != "base"
        ]
    return rows


def normalize_serials(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    for row in rows:
        normalized = []
        for name, serial in row.parallels:
            if serial:
                serial = serial.lstrip("0") or "0"
            normalized.append((name, serial))
        row.parallels = normalized
    return rows


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
    rows = remove_redundant_base(rows)
    rows = normalize_serials(rows)
    rows = dedupe_parallels(rows)
    return rows
