"""
Phase 5: clean each raw CardRecord into a RawOccurrence - per-row data
with all the per-record cleaning applied (year/brand/set split,
card_number cleaned + prefix extracted, player name split via Primary
Player). Grouping by card identity and building the final Insert/
Parallel/Sub_Type split happens in Phase 6 (merge.py), because Insert is
computed from ALL of a card's occurrences together (the text common to
every print version of that card), not from any single row in isolation.

Field mapping (per Brandon, 2026-06-28 through 2026-06-29):
    - year: parsed from the leading 4 digits of the website's Set string.
    - brand: the first word remaining after the year is stripped.
    - set: everything else after the brand (can be blank - that's fine,
      better than repeating the brand).
    - card_number: "#" stripped. If the number has a trailing run of
      digits (e.g. "T91-1", "TBC15"), everything before that run is a
      prefix that later gets prepended to the card's Insert. Purely
      numeric numbers (e.g. "517") get no prefix.
    - player: normally just the website's Name column. If a "Primary
      Player" was supplied via context (the whole batch is filtered to
      one player) and that name is found inside Name, player becomes
      exactly that name and everything else in Name (with the player's
      name removed) becomes "leftover text" that later folds into
      sub_type. If not found, Name is left completely as-is.
    - type, sport: fixed via context (Type is always "Sports" for BSC).
    - team, section: supplied via context, optional.

PR (Print Run) is treated exactly like SN (Serial Numbered) - both
extract into serial the same way, neither is the card's printed
designation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from scraper.card_record import CardRecord

SERIAL_PATTERN = re.compile(r"(?:SN|PR)(\d+)")
AUTOGRAPH_PATTERN = re.compile(r"\bAU\b")
SET_YEAR_PATTERN = re.compile(r"^\s*(\d{4})\s+(.*)$")
TRAILING_SLASH_SERIAL_PATTERN = re.compile(r"^(.*)/\s*(\d+)\s*$")
CARD_NUMBER_PREFIX_PATTERN = re.compile(r"^(.*?)(\d+)$")
WHITESPACE_PATTERN = re.compile(r"\s+")

# Words that get normalized to their singular form wherever they appear
# in insert/parallel text - "Refractors" -> "Refractor",
# "SuperFractors" -> "SuperFractor", "Prizms" -> "Prizm". This does NOT
# drop the word - e.g. "Black Refractors" stays "Black Refractor", it
# just loses the trailing "s". (An earlier version of this rule also
# dropped a standalone trailing "Refractor" entirely - that's been
# removed because it conflicted with real data: "Anime Black Refractors"
# needs to become "Black Refractor", not just "Black".)
PLURAL_TERM_PATTERN = re.compile(r"\b(Prizms|\w*[Ff]ractors)\b")


@dataclass
class RawOccurrence:
    """One cleaned website row, not yet grouped or split into
    Insert/Parallel/Sub_Type. card_number_prefix and section are
    duplicated onto every row in a group, which is harmless since
    they're always identical within a group."""
    type: str
    sport: str
    year: str
    brand: str
    set: str
    card_number: str
    card_number_prefix: str
    player: str
    team: str
    section: str
    variant_name: str  # "" for Base, otherwise the website's Variant Name
    attributes: str
    leftover_name_text: str  # leftover from Primary Player extraction


def parse_set(set_text: str) -> tuple[str, str, str]:
    """'2026 Panini Prizm' -> ('2026', 'Panini', 'Prizm').
    '2026 Bowman' -> ('2026', 'Bowman', '') - brand is just the first
    word after the year, everything else is set (blank if nothing
    remains)."""
    if not set_text:
        return "", "", ""
    match = SET_YEAR_PATTERN.match(set_text)
    if not match:
        words = set_text.strip().split()
        if not words:
            return "", "", ""
        return "", words[0], " ".join(words[1:])

    year = match.group(1)
    remainder_words = match.group(2).strip().split()
    if not remainder_words:
        return year, "", ""
    brand = remainder_words[0]
    set_value = " ".join(remainder_words[1:])
    return year, brand, set_value


def clean_card_number(card_number: str) -> str:
    """Strip a leading '#'. Otherwise unchanged."""
    if not card_number:
        return ""
    return card_number.lstrip("#").strip()


def extract_card_number_prefix(card_number: str) -> str:
    """'T91-1' -> 'T91-'. 'TBC15' -> 'TBC'. '517' -> ''. '12P5' -> '12P'."""
    if not card_number:
        return ""
    match = CARD_NUMBER_PREFIX_PATTERN.match(card_number)
    if match:
        return match.group(1)
    return ""


def split_primary_player(name_text: str, primary_player: str) -> tuple[str, str]:
    """If primary_player is found inside name_text, return
    (primary_player, leftover_text_with_it_removed). If primary_player
    is blank or not found, return (name_text, "") unchanged."""
    if not primary_player:
        return name_text, ""

    idx = name_text.lower().find(primary_player.lower())
    if idx == -1:
        return name_text, ""

    before = name_text[:idx]
    after = name_text[idx + len(primary_player):]
    leftover = WHITESPACE_PATTERN.sub(" ", before + after).strip()
    return primary_player, leftover


def normalize_plural_terms(text: str) -> str:
    """'Refractors' -> 'Refractor'. 'SuperFractors' -> 'SuperFractor'.
    'Prizms' -> 'Prizm'. Hyphens treated as spaces; whitespace collapsed.
    Does NOT drop any word - only singularizes."""
    if not text:
        return text
    normalized = text.replace("-", " ")
    normalized = PLURAL_TERM_PATTERN.sub(lambda m: m.group(0)[:-1], normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


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


def clean_variant_name(record: CardRecord) -> tuple[str, str]:
    """Returns (cleaned_variant_name, fallback_serial). Blank for Base
    or '-'. Handles the defensive 'Name /digits' fallback split too."""
    is_base = record.variant.strip().lower() == "base"
    text = "" if is_base else (record.variant_name or "").strip()
    if text == "-":
        text = ""
    text, fallback_serial = split_trailing_slash_serial(text)
    return text, fallback_serial


def build_raw_occurrence(record: CardRecord, context: dict | None = None) -> tuple[RawOccurrence, str]:
    """Returns (RawOccurrence, fallback_serial_from_slash_notation)."""
    context = context or {}
    year, brand, set_value = parse_set(record.set)

    card_number = clean_card_number(record.card_number)
    card_number_prefix = extract_card_number_prefix(card_number)

    primary_player = context.get("primary_player", "")
    player, leftover_name_text = split_primary_player(record.name, primary_player)

    variant_name, fallback_serial = clean_variant_name(record)

    occurrence = RawOccurrence(
        type=context.get("type", ""),
        sport=context.get("sport", ""),
        year=year,
        brand=brand,
        set=set_value,
        card_number=card_number,
        card_number_prefix=card_number_prefix,
        player=player,
        team=context.get("team", ""),
        section=context.get("section", ""),
        variant_name=variant_name,
        attributes=record.attributes,
        leftover_name_text=leftover_name_text,
    )
    return occurrence, fallback_serial


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[tuple[RawOccurrence, str]]:
    return [build_raw_occurrence(r, context) for r in records]
