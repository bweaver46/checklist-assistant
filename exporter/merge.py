"""
Phase 6: merge rows that represent the same physical card design but
different print occurrences (insert/sub_type/serial combos).

Rows are merged if everything except `occurrences` matches
(see ChecklistRow.merge_key). Order of first appearance is preserved.
"""

from __future__ import annotations

from collections import OrderedDict

from exporter.checklist_template import ChecklistRow


def merge_parallels(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    merged: "OrderedDict[tuple, ChecklistRow]" = OrderedDict()

    for row in rows:
        key = row.merge_key()
        if key not in merged:
            merged[key] = ChecklistRow(
                type=row.type,
                sport=row.sport,
                year=row.year,
                brand=row.brand,
                set=row.set,
                card_number=row.card_number,
                player=row.player,
                team=row.team,
                occurrences=list(row.occurrences),
            )
        else:
            merged[key].occurrences.extend(row.occurrences)

    return list(merged.values())
