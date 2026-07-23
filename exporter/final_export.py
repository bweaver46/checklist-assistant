"""
Phase 8: write the final checklist CSV - must match ColLock's import
template exactly.

Updated 2026-07-22 for ColLock's new import schema (was: type, sub_type,
year, brand, set, insert, attributes, card_number, player, team, base,
base_serial). Two real changes, not just a rename:
  1. The "type" column is dropped entirely - ColLock's new template has
     no equivalent column. The value is still tracked internally on
     ChecklistRow (used elsewhere, e.g. merge.py's grouping key) - it's
     just no longer written out.
  2. "Attributes" moved from before card_number to after Team (see
     HEADER_MAP below for the exact new order).

Column mapping (internal attribute -> external header):
    sub_type    -> Sport
    year        -> Year
    brand       -> Brand
    set         -> Set name
    insert      -> Insert / subset
    card_number -> Card number
    player      -> Player / card name
    team        -> Team
    attributes  -> Attributes
    base        -> Base
    base_serial -> Serial

Then parallel_1, serial_1, parallel_2, serial_2, ... expanded to
however many parallels the widest card in this batch actually has (at
least one pair, even if every card in the batch has zero parallels).
Every parallel_N column is always paired with a serial_N column, even
if serial_N is blank.
"""

from __future__ import annotations

import csv

from exporter.checklist_template import ChecklistRow

# (internal ChecklistRow attribute, external CSV header) in the exact
# order ColLock's template expects. "type" is intentionally excluded -
# see module docstring.
HEADER_MAP = [
    ("sub_type", "Sport"),
    ("year", "Year"),
    ("brand", "Brand"),
    ("set", "Set name"),
    ("insert", "Insert / subset"),
    ("card_number", "Card number"),
    ("player", "Player / card name"),
    ("team", "Team"),
    ("attributes", "Attributes"),
    ("base", "Base"),
    ("base_serial", "Serial"),
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

    columns = [header for _, header in HEADER_MAP] + parallel_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {header: getattr(row, attr) for attr, header in HEADER_MAP}
            for i in range(1, max_parallels + 1):
                if i <= len(row.parallels):
                    parallel, serial = row.parallels[i - 1]
                else:
                    parallel, serial = "", ""
                record[f"parallel_{i}"] = parallel
                record[f"serial_{i}"] = serial
            writer.writerow(record)

