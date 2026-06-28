"""
Phase 8: write the final checklist CSV.

Columns are the per-card identity fields plus insert_1/sub_type_1/serial_1,
insert_2/sub_type_2/serial_2, ... expanded to however many occurrences the
widest card in this batch actually has.
"""

import csv

from exporter.checklist_template import ChecklistRow

BASE_COLUMNS = [
    "type", "sport", "year", "brand", "set", "card_number", "player", "team",
]


def write_final_csv(rows: list[ChecklistRow], path: str) -> None:
    max_occurrences = max((len(row.occurrences) for row in rows), default=0)

    occurrence_columns: list[str] = []
    for i in range(1, max_occurrences + 1):
        occurrence_columns += [f"insert_{i}", f"sub_type_{i}", f"serial_{i}"]

    columns = BASE_COLUMNS + occurrence_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {col: getattr(row, col) for col in BASE_COLUMNS}
            for i, (insert, sub_type, serial) in enumerate(row.occurrences, start=1):
                record[f"insert_{i}"] = insert
                record[f"sub_type_{i}"] = sub_type
                record[f"serial_{i}"] = serial
            writer.writerow(record)
