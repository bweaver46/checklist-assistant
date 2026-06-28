"""
Phase 5: convert raw CardRecord objects into ChecklistRow objects.

Still one row per website row at this point - merging happens in Phase 6.

*** This mapping is a best guess. ***
BuySportsCards' "variant" field is assumed to hold something like
"Gold /50", which split_serial() splits into a parallel name and a serial
number. sport / year / brand / type / insert / sub_type / team are NOT
present in the row data the vision doc describes, so they're pulled from
`context` - metadata about the current search/filter that has to be
supplied some other way (read from the page header, parsed from the URL,
or typed in by Brandon before running extraction). Revisit this once we
have real extracted rows to look at.
"""

import re

from scraper.card_record import CardRecord
from exporter.checklist_template import ChecklistRow

SERIAL_PATTERN = re.compile(r"/(\d+)")


def split_serial(text: str) -> tuple[str, str]:
    """'Gold /50' -> ('Gold', '50'). No serial found -> (text, '')."""
    if not text:
        return "", ""
    match = SERIAL_PATTERN.search(text)
    serial = match.group(1) if match else ""
    name = SERIAL_PATTERN.sub("", text).strip()
    return name, serial


def convert_record(record: CardRecord, context: dict | None = None) -> ChecklistRow:
    context = context or {}
    row = ChecklistRow(
        type=context.get("type", ""),
        sport=context.get("sport", ""),
        year=context.get("year", ""),
        brand=context.get("brand", ""),
        set=record.set or context.get("set", ""),
        insert=context.get("insert", ""),
        sub_type=context.get("sub_type", ""),
        card_number=record.card_number,
        player=record.name,
        team=context.get("team", ""),
    )
    parallel_name, serial = split_serial(record.variant)
    if parallel_name:
        row.parallels.append((parallel_name, serial))
    return row


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[ChecklistRow]:
    return [convert_record(r, context) for r in records]
