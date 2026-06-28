"""
Phase 5: convert raw CardRecord objects into ChecklistRow objects.

Still one row per website row at this point - merging happens in Phase 6.

Confirmed against the live BuySportsCards table (2026-06-28):
    - `variant` is a category: "Base" or "Insert". Base rows get no
      parallel at all.
    - `variant_name` holds the actual parallel/insert name, e.g.
      "Anime Red Refractors". "-" means not applicable.
    - `attributes` holds serial number as "SN<digits>" and/or an
      autograph flag "AU", comma-separated when both present, e.g.
      "AU, SN150". "-" means no attributes.

*** OPEN QUESTION for Brandon: how should autographed cards (AU) show up
*** in the final checklist? Right now the parallel name gets " (AU)"
*** appended as a placeholder. If your checklist format wants a separate
*** AU column instead, say so and this gets a one-line fix.

sport / year / brand / type / insert / sub_type / team are NOT present in
the row data at all - they come from `context`, metadata about the
current search that has to be supplied some other way (read from the
page header/URL, or typed in before extracting). Still unresolved.
"""

import re

from scraper.card_record import CardRecord
from exporter.checklist_template import ChecklistRow

SERIAL_PATTERN = re.compile(r"SN(\d+)")
AUTOGRAPH_PATTERN = re.compile(r"\bAU\b")


def parse_attributes(attributes: str) -> tuple[str, bool]:
    """'AU, SN150' -> ('150', True). 'SN10' -> ('10', False). '-' -> ('', False)."""
    if not attributes or attributes == "-":
        return "", False
    serial_match = SERIAL_PATTERN.search(attributes)
    serial = serial_match.group(1) if serial_match else ""
    is_autograph = bool(AUTOGRAPH_PATTERN.search(attributes))
    return serial, is_autograph


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

    is_base = record.variant.strip().lower() == "base"
    if not is_base:
        parallel_name = record.variant_name.strip()
        if parallel_name and parallel_name != "-":
            serial, is_autograph = parse_attributes(record.attributes)
            if is_autograph:
                parallel_name = f"{parallel_name} (AU)"
            row.parallels.append((parallel_name, serial))

    return row


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[ChecklistRow]:
    return [convert_record(r, context) for r in records]
