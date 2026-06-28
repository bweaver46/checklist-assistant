"""
Phase 5: convert raw CardRecord objects into ChecklistRow objects.

Still one row per website row at this point - merging happens in Phase 6.

Field mapping (per Brandon, 2026-06-28):
    - year, brand: parsed out of the website's "Set" string (e.g.
      "2026 Bowman" -> year="2026", brand="Bowman"). UNLIKE earlier
      versions, the `set` column itself now holds just the brand part
      (e.g. "Bowman"), not the year-prefixed full string - year already
      has its own column, no need to repeat it.
    - card_number: the website's Card # with a leading "#" stripped.
      Otherwise unchanged.
    - insert: the website's Variant Name, blank for Base, PLUS a
      prefix derived from card_number: whatever text comes before the
      trailing run of digits at the end of the card number (e.g.
      "T91-1" -> prefix "T91-", "TBC15" -> prefix "TBC", "517" -> no
      prefix, it's purely numeric). That prefix gets prepended to the
      insert text, space-separated, since it identifies which
      subset/era a card belongs to within a player-pull search.
    - sub_type: derived from Attributes, the Section context value, and
      (new) any leftover text from the Name column after the Primary
      Player's name is extracted out of it (see below).
        - "AU" -> "Autograph", UNLESS the word "Autograph" already
          appears in the set, this occurrence's insert text, the
          section, or the leftover Name text - in which case it's
          dropped as redundant.
        - "PR" is just an alternate label for a serial number ("Print
          Run") - not a distinct sub_type category. PR<digits> is
          treated exactly like SN<digits>.
    - serial: the digits from Attributes' "SN<digits>" or "PR<digits>" token.
    - player: normally just the website's Name column, UNCHANGED. BUT
      if a "Primary Player" was supplied via context (because the whole
      search/batch was filtered to one player), and that name is found
      inside the Name text, `player` becomes exactly that name and
      everything else in Name (with the player's name removed) gets
      folded into sub_type instead. Handles cases like
      "Stars Align (Mike Trout Zach Netto) CPC" when searching Mike
      Trout specifically -> player="Mike Trout",
      sub_type gets "Stars Align (Zach Netto) CPC". If the Primary
      Player text isn't found in Name, Name is left completely as-is
      (no silent data loss).
    - type, sport: NOT derivable from the row data - supplied via
      `context`, which the app now prompts for once per extraction run.
    - team: not present in row data, supplied via `context`. Optional -
      blank is fine.
    - section: NOT present in row data either, supplied via `context`.
      For "continuation numbering" (e.g. a Prospects/Series 2 subsection
      that continues a base set's numbering rather than restarting at
      #1) - the `set` and `card_number` stay exactly as the website
      gives them (never renumbered), and the section name goes into
      `sub_type` instead.

A truly plain Base row is dropped entirely (Phase 7's "remove redundant
Base") ONLY if there is nothing at all to record: no attributes, no
section, AND no card-number prefix. If any of those exist, the row is
kept (with insert/sub_type built from whatever's available) so that
information doesn't get silently lost.

Defensive fallback: if a Variant Name ever shows up as "Name /digits"
(slash-serial jammed into the name) rather than as separate Variant
Name + Attributes columns, that trailing "/digits" gets split off into
serial too. Not needed for any real row seen so far, but cheap insurance.
"""

from __future__ import annotations

import re

from scraper.card_record import CardRecord
from exporter.checklist_template import ChecklistRow

# SN (Serial Numbered) and PR (Print Run) are the same concept under two
# different labels - both mean "this many were made", neither is the
# card's printed designation. Both extract into `serial` the same way.
SERIAL_PATTERN = re.compile(r"(?:SN|PR)(\d+)")
AUTOGRAPH_PATTERN = re.compile(r"\bAU\b")
SET_YEAR_PATTERN = re.compile(r"^\s*(\d{4})\s+(.*)$")
TRAILING_SLASH_SERIAL_PATTERN = re.compile(r"^(.*)/\s*(\d+)\s*$")
CARD_NUMBER_PREFIX_PATTERN = re.compile(r"^(.*?)(\d+)$")
WHITESPACE_PATTERN = re.compile(r"\s+")
TRAILING_REFRACTOR_PATTERN = re.compile(r"\s+Refractors?\s*$", re.IGNORECASE)
PLURAL_TERM_PATTERN = re.compile(r"\b(Prizms?|Refractors?)\b", re.IGNORECASE)


def _normalize_plural_term(match: "re.Match") -> str:
    word = match.group(0).lower()
    return "Prizm" if word.startswith("prizm") else "Refractor"


def normalize_insert_name(name: str) -> str:
    """'Black-Wave' -> 'Black Wave'. 'Blue Mojo Refractor' -> 'Blue Mojo'.
    'Prizms'/'Refractors' -> 'Prizm'/'Refractor' wherever they remain.
    Collapses/trims whitespace throughout. This runs on the
    variant-name-derived part of an occurrence's insert text BEFORE the
    card-number prefix gets prepended - the prefix's own hyphen (e.g.
    "T91-") must never get stripped by this rule."""
    if not name:
        return name

    normalized = name.replace("-", " ")
    normalized = TRAILING_REFRACTOR_PATTERN.sub("", normalized)
    normalized = PLURAL_TERM_PATTERN.sub(_normalize_plural_term, normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def parse_set(set_text: str) -> tuple[str, str]:
    """'2026 Bowman' -> ('2026', 'Bowman'). No leading year -> ('', set_text)."""
    if not set_text:
        return "", ""
    match = SET_YEAR_PATTERN.match(set_text)
    if match:
        return match.group(1), match.group(2).strip()
    return "", set_text.strip()


def clean_card_number(card_number: str) -> str:
    """Strip a leading '#'. Otherwise unchanged."""
    if not card_number:
        return ""
    return card_number.lstrip("#").strip()


def extract_card_number_prefix(card_number: str) -> str:
    """'T91-1' -> 'T91-'. 'TBC15' -> 'TBC'. '517' -> ''. '12P5' -> '12P'.
    The trailing run of digits is the card's number within its set;
    everything before it is a prefix identifying the subset/era."""
    if not card_number:
        return ""
    match = CARD_NUMBER_PREFIX_PATTERN.match(card_number)
    if match:
        return match.group(1)
    return ""


def split_primary_player(name_text: str, primary_player: str) -> tuple[str, str]:
    """If primary_player is found inside name_text, return
    (primary_player, leftover_text_with_it_removed). If primary_player
    is blank or not found, return (name_text, "") unchanged - no data
    is ever silently dropped."""
    if not primary_player:
        return name_text, ""

    idx = name_text.lower().find(primary_player.lower())
    if idx == -1:
        return name_text, ""

    before = name_text[:idx]
    after = name_text[idx + len(primary_player):]
    leftover = WHITESPACE_PATTERN.sub(" ", before + after).strip()
    return primary_player, leftover


def build_sub_type(
    attributes: str,
    set_text: str,
    insert_text: str,
    section: str = "",
    extra_text: str = "",
) -> str:
    """Derive sub_type from the Section context value, any leftover Name
    text (after Primary Player extraction), and Attributes - avoiding a
    redundant 'Autograph' if that word already appears anywhere else in
    this occurrence's other text. SN/PR never contribute to sub_type -
    they're serial info, handled by parse_serial instead."""
    parts = []
    section = (section or "").strip()
    extra_text = (extra_text or "").strip()

    if section:
        parts.append(section)
    if extra_text:
        parts.append(extra_text)

    already_says_autograph = any(
        "autograph" in (text or "").lower()
        for text in (set_text, insert_text, section, extra_text)
    )
    if (
        attributes
        and attributes != "-"
        and AUTOGRAPH_PATTERN.search(attributes)
        and not already_says_autograph
    ):
        parts.append("Autograph")

    return ", ".join(parts)


def parse_serial(attributes: str) -> str:
    if not attributes:
        return ""
    match = SERIAL_PATTERN.search(attributes)
    return match.group(1) if match else ""


def split_trailing_slash_serial(text: str) -> tuple[str, str]:
    """'Gold /50' -> ('Gold', '50'). No trailing slash-serial -> (text, '')."""
    if not text:
        return text, ""
    match = TRAILING_SLASH_SERIAL_PATTERN.match(text)
    if match:
        return match.group(1).strip(), match.group(2)
    return text, ""


def is_plain_base(
    record: CardRecord,
    section: str = "",
    card_number_prefix: str = "",
    leftover_name_text: str = "",
) -> bool:
    """A row is droppable (Phase 7's 'remove redundant Base') only if
    there's truly nothing to record: it's a Base row, it has no
    attributes, no section context, no card-number prefix, AND no
    leftover Name text from Primary Player extraction worth keeping."""
    return (
        record.variant.strip().lower() == "base"
        and (not record.attributes or record.attributes.strip() == "-")
        and not (section or "").strip()
        and not card_number_prefix
        and not (leftover_name_text or "").strip()
    )


def convert_record(record: CardRecord, context: dict | None = None) -> ChecklistRow:
    context = context or {}
    year, brand = parse_set(record.set)

    card_number = clean_card_number(record.card_number)
    card_number_prefix = extract_card_number_prefix(card_number)

    primary_player = context.get("primary_player", "")
    player, leftover_name_text = split_primary_player(record.name, primary_player)

    row = ChecklistRow(
        type=context.get("type", ""),
        sport=context.get("sport", ""),
        year=year,
        brand=brand,
        set=brand,
        card_number=card_number,
        player=player,
        team=context.get("team", ""),
    )

    if not is_plain_base(record, context.get("section", ""), card_number_prefix, leftover_name_text):
        is_base = record.variant.strip().lower() == "base"
        insert_text = "" if is_base else (record.variant_name or "").strip()
        if insert_text == "-":
            insert_text = ""

        insert_text, fallback_serial = split_trailing_slash_serial(insert_text)
        insert_text = normalize_insert_name(insert_text)

        if card_number_prefix:
            insert_text = f"{card_number_prefix} {insert_text}".strip()
            insert_text = WHITESPACE_PATTERN.sub(" ", insert_text)

        section = context.get("section", "")
        sub_type = build_sub_type(
            record.attributes, record.set, insert_text, section, leftover_name_text
        )
        serial = parse_serial(record.attributes) or fallback_serial
        row.occurrences.append((insert_text, sub_type, serial))

    return row


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[ChecklistRow]:
    return [convert_record(r, context) for r in records]
