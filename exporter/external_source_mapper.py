"""
External Source Mapper

Beckett and TCDB parsers already produce nearly-final rows (unlike
BSC's raw per-occurrence data, which needs convert.py + merge.py's
Insert/Parallel derivation from scratch). This module maps those raw
row dicts straight onto ChecklistRow.

year/brand/set reuse the exact same parse_set() logic BSC's per-row
Set text goes through (including brand_set_exceptions.csv) - sourced
here from a single "Product" text Brandon types once per extraction
(e.g. "2025 Bowman", "1972 Topps"), since neither Beckett nor TCDB
gives a clean brand/set string separate from the sport the way BSC's
own Set column does.
"""

from __future__ import annotations

from exporter.convert import parse_set
from exporter.checklist_template import ChecklistRow

DEFAULT_TYPE = "Sports"  # matches app/main_window.py's DEFAULT_TYPE


def build_checklist_rows(rows: list[dict], context: dict) -> list[ChecklistRow]:
    """context needs: 'product' (e.g. '2025 Bowman') and 'sport'
    (e.g. 'Baseball')."""
    year, brand, set_value = parse_set(context.get("product", ""))
    sport = context.get("sport", "")

    checklist_rows = []
    for row in rows:
        checklist_rows.append(ChecklistRow(
            type=DEFAULT_TYPE,
            sub_type=sport,
            year=year,
            brand=brand,
            set=set_value,
            insert=row.get("insert", ""),
            attributes=row.get("attributes", ""),
            card_number=row.get("card_number", ""),
            player=row.get("player", ""),
            team=row.get("team", ""),
            base="",
            base_serial=row.get("base_serial", ""),
            parallels=row.get("parallels", []),
        ))
    return checklist_rows
