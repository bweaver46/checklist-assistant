"""
Phase 8: write the final checklist CSV - the exact format your Check List
Builder expects.

Columns are the base template fields plus parallel_1/serial_1,
parallel_2/serial_2, ... expanded to however many parallels the widest
row in this batch actually has.
"""

import csv

from exporter.checklist_template import ChecklistRow

BASE_COLUMNS = [
    "type", "sport", "year", "brand", "set",
    "insert", "sub_type", "card_number", "player", "team",
]


def write_final_csv(rows: list[ChecklistRow], path: str) -> None:
    max_parallels = max((len(row.parallels) for row in rows), default=0)

    parallel_columns: list[str] = []
    for i in range(1, max_parallels + 1):
        parallel_columns += [f"parallel_{i}", f"serial_{i}"]

    columns = BASE_COLUMNS + parallel_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {col: getattr(row, col) for col in BASE_COLUMNS}
            for i, (name, serial) in enumerate(row.parallels, start=1):
                record[f"parallel_{i}"] = name
                record[f"serial_{i}"] = serial
            writer.writerow(record)
