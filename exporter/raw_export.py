"""
Phase 4: write raw records to a CSV exactly as extracted.

This is a debugging tool. If something looks wrong in the final checklist,
compare this raw CSV against the website to find where the discrepancy
was introduced.
"""

import csv

from scraper.card_record import CardRecord


def write_raw_csv(records: list[CardRecord], path: str) -> None:
    columns = CardRecord.csv_columns()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())
