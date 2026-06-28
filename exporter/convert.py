"""
Phase 5: convert raw CardRecord objects into ChecklistRow objects.

Still one row per website row at this point - merging happens in Phase 6.

Field mapping (per Brandon, 2026-06-28):
    - year, brand: parsed out of the website's "Set" string (e.g.
      "2026 Bowman" -> year="2026", brand="Bowman"). `set` itself keeps
      the full original string.
    - insert: the website's Variant Name, blank for Base.
    - sub_type: derived from Attributes.
        - "AU" -> "Autograph", UNLESS the word "Autograph" already
          appears in the set or this occurrence's insert text, in which
          case it's dropped as redundant.
        - "PR" is just an alternate label for a serial number ("Print
          Run") - it is NOT printed on the card itself and is NOT a
          distinct sub_type category. PR<digits> is treated exactly
          like SN<digits>: the number goes into `serial`, nothing goes
          into `sub_type`.
    - serial: the digits from Attributes' "SN<digits>" or "PR<digits>" token.
    - type, sport: NOT derivable from the row data - supplied via
      `context`, which the app now prompts for once per extraction run.
    - team: still unresolved - not present in row data, not yet asked
      for. Left blank for now.

A truly plain Base row (variant == "Base" and attributes == "-") is
dropped entirely (Phase 7's "remove redundant Base"). A Base row that
DOES carry an attribute (e.g. a serial-numbered version BSC still
buckets under "Base") is kept, with insert left blank as instructed.
"""

import re

from scraper.card_record import CardRecord
from exporter.checklist_template import ChecklistRow

# SN (Serial Numbered) and PR (Print Run) are the same concept under two
# different labels - both mean "this many were made", neither is the
# card's printed designation. Both extract into `serial` the same way.
SERIAL_PATTERN = re.compile(r"(?:SN|PR)(\d+)")
AUTOGRAPH_PATTERN = re.compile(r"\bAU\b")
SET_YEAR_PATTERN = re.compile(r"^\s*(\d{4})\s+(.*)$")


def parse_set(set_text: str) -> tuple[str, str]:
    """'2026 Bowman' -> ('2026', 'Bowman'). No leading year -> ('', set_text)."""
    if not set_text:
        return "", ""
    match = SET_YEAR_PATTERN.match(set_text)
    if match:
        return match.group(1), match.group(2).strip()
    return "", set_text.strip()


def build_sub_type(attributes: str, set_text: str, insert_text: str) -> str:
    """Derive sub_type from Attributes, avoiding a redundant 'Autograph'
    if that word already appears in the set or this occurrence's insert.
    SN/PR never contribute to sub_type - they're serial info, handled by
    parse_serial instead."""
    if not attributes or attributes == "-":
        return ""

    already_says_autograph = (
        "autograph" in (set_text or "").lower()
        or "autograph" in (insert_text or "").lower()
    )
    if AUTOGRAPH_PATTERN.search(attributes) and not already_says_autograph:
        return "Autograph"

    return ""


def parse_serial(attributes: str) -> str:
    if not attributes:
        return ""
    match = SERIAL_PATTERN.search(attributes)
    return match.group(1) if match else ""


def is_plain_base(record: CardRecord) -> bool:
    return (
        record.variant.strip().lower() == "base"
        and (not record.attributes or record.attributes.strip() == "-")
    )


def convert_record(record: CardRecord, context: dict | None = None) -> ChecklistRow:
    context = context or {}
    year, brand = parse_set(record.set)

    row = ChecklistRow(
        type=context.get("type", ""),
        sport=context.get("sport", ""),
        year=year,
        brand=brand,
        set=record.set,
        card_number=record.card_number,
        player=record.name,
        team=context.get("team", ""),
    )

    if not is_plain_base(record):
        is_base = record.variant.strip().lower() == "base"
        insert_text = "" if is_base else (record.variant_name or "").strip()
        if insert_text == "-":
            insert_text = ""
        sub_type = build_sub_type(record.attributes, record.set, insert_text)
        serial = parse_serial(record.attributes)
        row.occurrences.append((insert_text, sub_type, serial))

    return row


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[ChecklistRow]:
    return [convert_record(r, context) for r in records]
