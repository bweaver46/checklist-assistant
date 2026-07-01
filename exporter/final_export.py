"""
Phase 8: write the final checklist CSV - must match the template
exactly: type, sport, year, brand, set, insert, sub_type, card_number,
player, team, parallel_1, serial_1, parallel_2, serial_2, ... expanded
to however many parallels the widest card in this batch actually has.
Every parallel_N column is always paired with a serial_N column, even
if serial_N is blank.
"""

from __future__ import annotations

import csv

from exporter.checklist_template import ChecklistRow

BASE_COLUMNS = [
    "type", "sub_type", "year", "brand", "set", "insert", "attributes",
    "card_number", "player", "team", "base", "base_serial",
]


def sort_rows_by_brand(rows: list[ChecklistRow]) -> list[ChecklistRow]:
    """Sort by brand first, then set/year/card_number for a stable,
    predictable order within each brand."""
    return sorted(rows, key=lambda r: (r.brand, r.set, r.year, r.card_number))


def write_final_csv(rows: list[ChecklistRow], path: str) -> None:
    max_parallels = max((len(row.parallels) for row in rows), default=0)
    max_parallels = max(max_parallels, 1)  # template always has at least parallel_1/serial_1

    parallel_columns: list[str] = []
    for i in range(1, max_parallels + 1):
        parallel_columns += [f"parallel_{i}", f"serial_{i}"]

    columns = BASE_COLUMNS + parallel_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {col: getattr(row, col) for col in BASE_COLUMNS}
            for i in range(1, max_parallels + 1):
                if i <= len(row.parallels):
                    parallel, serial = row.parallels[i - 1]
                else:
                    parallel, serial = "", ""
                record[f"parallel_{i}"] = parallel
                record[f"serial_{i}"] = serial
            writer.writerow(record)
