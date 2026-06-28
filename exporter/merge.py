"""
Phase 6: merge rows that represent the same card but different parallels.

Mike Trout / Base
Mike Trout / Gold /50
Mike Trout / Red /5

becomes one Mike Trout row with parallel_1=Gold/50, parallel_2=Red/5.

Rows are merged if everything except the parallel list matches
(see ChecklistRow.merge_key). Order of first appearance is preserved.
"""

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
                insert=row.insert,
                sub_type=row.sub_type,
                card_number=row.card_number,
                player=row.player,
                team=row.team,
                parallels=list(row.parallels),
            )
        else:
            merged[key].parallels.extend(row.parallels)

    return list(merged.values())
