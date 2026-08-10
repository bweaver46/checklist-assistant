"""
Phase 4: write raw records to a CSV exactly as extracted.

This is a debugging tool. If something looks wrong in the final checklist,
compare this raw CSV against the website to find where the discrepancy
was introduced.

card_number gets a leading apostrophe here (Brandon, 2026-08-07) so
spreadsheet apps (Excel/Numbers/Sheets) treat it as forced text instead
of silently reinterpreting something like "WST-1" as a number/date and
mangling it (seen as "-WST 1.00" after a round trip through a
spreadsheet app - confirmed against BSC's own site, which shows the
clean "WST-1" text with no such formatting). Excel/Numbers strip the
leading apostrophe from what's DISPLAYED, so this is invisible if
opened there - the raw text on disk just has it.

This is intentionally NOT done in exporter/final_export.py - that file
is read directly by ColLock's bulk importer, which (unlike Excel) has
no concept of a "forced text" apostrophe marker; it would import the
apostrophe as a literal character in the card number instead of
stripping it, corrupting the actual import. This file, by contrast, is
never re-read by anything - it's purely for a human to open and
compare against the live site - so it's safe to make it
spreadsheet-proof.
"""

from __future__ import annotations

import csv

from scraper.card_record import CardRecord


def excel_safe_card_number(card_number: str) -> str:
    """Prefix with a leading apostrophe so spreadsheet apps treat this
    as text and don't reinterpret/reformat it as a number or date.
    Blank stays blank - nothing to protect."""
    if not card_number:
        return card_number
    return f"'{card_number}"


def write_raw_csv(records: list[CardRecord], path: str) -> None:
    columns = CardRecord.csv_columns()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for record in records:
            row = record.to_dict()
            row["card_number"] = excel_safe_card_number(row["card_number"])
            writer.writerow(row)
