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
    - brand: the first word remaining after the year is stripped, UNLESS
      it matches a known exception (see settings/brand_set_exceptions.csv) -
      some product lines don't follow the simple first-word rule, e.g.
      "Finest" has no real brand word at all (it's a Topps product), and
      multi-word lines like "Topps Now", "Bowman's Best", "Stadium Club"
      would otherwise get split in the middle of their actual name.
    - set: everything else after the brand (can be blank - that's fine,
      better than repeating the brand) - UNLESS an exception applies, in
      which case the exception's own set value is used (which may
      legitimately repeat the brand, e.g. "Topps Now" / "Topps Now").
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

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from scraper.card_record import CardRecord

SERIAL_PATTERN = re.compile(r"(?:SN|PR)(\d+)")
AUTOGRAPH_PATTERN = re.compile(r"\bAU\b")
# Matches card numbers that are purely digits followed by a single
# lowercase letter suffix (e.g. "1b", "1c", "517b"). These are lettered
# variants of the same card (Short Prints, Variations) and should group
# with their base card rather than being treated as separate cards.
# Does NOT match structural lettered numbers like "BA-23" or "T91-1".
LETTER_VARIANT_PATTERN = re.compile(r'^(\d+)([a-z])$')
SET_YEAR_PATTERN = re.compile(r"^\s*(\d{4})(?:-\d{2,4})?\s+(.*)$")
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

# Editable in Excel/Numbers - re-saved as CSV, no code changes needed.
# Columns: pattern, brand, set. `pattern` is matched word-wise against
# the start of the Set text remaining after the year is stripped
# (case-insensitive). Longer patterns are checked first so e.g.
# "Topps Now" matches before any shorter, more general pattern would.
BRAND_SET_EXCEPTIONS_PATH = Path(__file__).resolve().parent.parent / "settings" / "brand_set_exceptions.csv"

_brand_set_exceptions_cache: list[tuple[list[str], str, str]] | None = None


def load_brand_set_exceptions() -> list[tuple[list[str], str, str]]:
    """Returns [(pattern_words, brand, set), ...], longest pattern
    first. Cached after first load. Missing file -> empty list, no
    crash - exceptions are an enhancement, not a requirement."""
    global _brand_set_exceptions_cache
    if _brand_set_exceptions_cache is not None:
        return _brand_set_exceptions_cache

    exceptions = []
    if BRAND_SET_EXCEPTIONS_PATH.exists():
        # utf-8-sig (not plain utf-8): Excel/Numbers often save CSV
        # with a leading BOM character, which otherwise silently
        # attaches itself to the first column name ("pattern" becomes
        # "\ufeffpattern"), making every row.get("pattern") return
        # None and the WHOLE file fail to load with no error. Safe
        # either way - utf-8-sig strips a BOM if present and behaves
        # identically to utf-8 when there isn't one.
        with open(BRAND_SET_EXCEPTIONS_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pattern = (row.get("pattern") or "").strip()
                brand = (row.get("brand") or "").strip()
                set_value = (row.get("set") or "").strip()
                if pattern:
                    exceptions.append((pattern.split(), brand, set_value.strip()))

    exceptions.sort(key=lambda e: len(e[0]), reverse=True)
    _brand_set_exceptions_cache = exceptions
    return exceptions


def match_brand_set_exception(remainder_words: list[str]) -> tuple[str, str] | None:
    """If remainder_words starts with a known exception pattern
    (case-insensitive, word-wise), return that exception's (brand, set).
    Any words in remainder_words AFTER the matched pattern get appended
    onto the exception's set value (e.g. pattern "UD" matched against
    "UD Series 1" -> set "Upper Deck Series 1", not just "Upper Deck" -
    nothing gets silently dropped). Otherwise None."""
    for pattern_words, brand, set_value in load_brand_set_exceptions():
        if len(remainder_words) < len(pattern_words):
            continue
        head = [w.lower() for w in remainder_words[: len(pattern_words)]]
        if head == [w.lower() for w in pattern_words]:
            leftover_words = remainder_words[len(pattern_words):]
            final_set = set_value
            if leftover_words:
                final_set = (set_value + " " + " ".join(leftover_words)).strip()
            return brand, final_set
    return None


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
    is_base: bool = False         # True when the website's Variant column read "Base"
    is_insert: bool = False       # True when the website's Variant column read "Insert" (as opposed to "Parallel")
    is_letter_variant: bool = False  # True when card number has a trailing letter (1b, 1c)
    description: str = ""         # from the Add page; used to build lettered variant parallel name


UNLICENSED_PATTERN = re.compile(r"\(unlicensed\)", re.IGNORECASE)


def parse_set(set_text: str) -> tuple[str, str, str]:
    """'2026 Panini Prizm' -> ('2026', 'Panini', 'Prizm').
    '2026 Bowman' -> ('2026', 'Bowman', '') - brand is just the first
    word after the year, everything else is set (blank if nothing
    remains) - UNLESS a known exception applies (see
    settings/brand_set_exceptions.csv), e.g. "Finest" -> brand "Topps",
    or "Topps Now" -> brand "Topps", set "Topps Now" (deliberately
    repeating, since that IS the correct full product name).

    Hard-coded rule (per Brandon, 2026-07-04, NOT in the CSV exceptions
    file on purpose): whenever the literal text "(unlicensed)" appears
    anywhere in set_text, brand is ALWAYS "Unlicensed" and the rest of
    the text (with the "(unlicensed)" marker removed, year still
    extracted normally if one's present) becomes the set - regardless
    of the normal first-word-is-brand rule or any exceptions entry.
    This can't live in the CSV because the surrounding wording varies
    per product ("The Press Box Collector's Choices of the 1980's
    (unlicensed)" -> brand "Unlicensed", set "The Press Box
    Collector's Choices of the 1980's") - only the word "unlicensed"
    itself is the reliable signal, not any specific product name."""
    if not set_text:
        return "", "", ""

    if UNLICENSED_PATTERN.search(set_text):
        remainder = UNLICENSED_PATTERN.sub("", set_text)
        remainder = WHITESPACE_PATTERN.sub(" ", remainder).strip()
        year_match = SET_YEAR_PATTERN.match(remainder)
        if year_match:
            return year_match.group(1), "Unlicensed", year_match.group(2).strip()
        return "", "Unlicensed", remainder

    match = SET_YEAR_PATTERN.match(set_text)
    if not match:
        words = set_text.strip().split()
        if not words:
            return "", "", ""
        exception = match_brand_set_exception(words)
        if exception:
            return "", exception[0], exception[1]
        return "", words[0], " ".join(words[1:])

    year = match.group(1)
    remainder_words = match.group(2).strip().split()
    if not remainder_words:
        return year, "", ""

    exception = match_brand_set_exception(remainder_words)
    if exception:
        return year, exception[0], exception[1]

    brand = remainder_words[0]
    set_value = " ".join(remainder_words[1:])
    return year, brand, set_value


def clean_card_number(card_number: str) -> str:
    """Strip a leading "'" and/or "#". BSC sometimes prefixes the raw
    card_number with a literal apostrophe (its own anti-Excel-
    autoformat trick, so a number like "206-FT" doesn't get silently
    reinterpreted as a date) ahead of the "#" - e.g. "'#206-FT". Only
    "#" was being stripped here, so that apostrophe survived straight
    through to the final export whenever BSC included it (2020 Panini
    Diamond Kings, confirmed against the raw export, Brandon
    2026-08-08 - #DK10 and #206-FT both came out as "'#DK10"/"'#206-FT"
    instead of "DK10"/"206-FT"). Strips any leading run of either
    character, in any order, not just one apostrophe then one hash."""
    if not card_number:
        return ""
    return re.sub(r"^['#]+", "", card_number).strip()


def extract_card_number_prefix(card_number: str) -> str:
    """Prefix extraction removed - prepending card number prefixes (e.g.
    'O-' from 'O-123') to Insert produced wrong output. Always blank."""
    return ""


NAME_PREFIXES = {"mc", "mac", "de", "la", "le", "di", "van", "von", "o"}


def split_concatenated_names(text: str) -> str:
    """BSC sometimes concatenates multiple player names with no separator:
    'Dave JollyJim PendletonKarl Spooner' -> 'Dave Jolly / Jim Pendleton / Karl Spooner'.

    The split point is wherever a lowercase letter is immediately followed
    by an uppercase letter with no space between them - that boundary is
    usually where one name ends and the next begins.

    A common surname prefix (Mc, Mac, De, La, Le, Di, Van, Von, O) sitting
    right before that boundary is NOT treated as a split point - e.g.
    "McGwire" has exactly this lowercase-then-uppercase shape internally
    ("Mc" + "Gwire") but is one name, not two. Previously any of these
    surnames got incorrectly split ("Mark Mc / Gwire", "Andrew Mc /
    Cutchen") - confirmed at real scale against a Brandon export (68 rows
    in one 2025 Allen & Ginter pull alone, 2026-08-15), not the rare edge
    case this function's docstring used to assume. Each whitespace-
    delimited token is scanned independently, checking the text since the
    last accepted split (or token start) against the prefix list before
    deciding to split there - so a genuinely concatenated run following a
    protected surname (e.g. a hypothetical "McGwireJohnSmith") still
    splits correctly after "McGwire", not before it.

    Remaining known limitation: a name with an internal capital that ISN'T
    one of these common prefixes (rare) can still split wrong - uncommon
    enough that manual correction stays simpler than enumerating every
    possible surname pattern."""
    if not text:
        return text

    def split_token(token: str) -> str:
        pieces: list[str] = []
        seg_start = 0
        for i in range(len(token) - 1):
            if token[i].islower() and token[i + 1].isupper():
                prefix = token[seg_start:i + 1]
                if prefix.lower() in NAME_PREFIXES:
                    continue
                pieces.append(prefix)
                seg_start = i + 1
        pieces.append(token[seg_start:])
        return " / ".join(pieces)

    result = " ".join(split_token(t) for t in text.split(" "))
    return WHITESPACE_PATTERN.sub(' ', result).strip()


def normalize_team_separators(team: str) -> str:
    """BSC sometimes returns multiple teams as a comma-separated string:
    'Milwaukee Braves, Milwaukee Braves, Brooklyn Dodgers'
    -> 'Milwaukee Braves / Milwaukee Braves / Brooklyn Dodgers'."""
    if not team:
        return team
    return team.replace(", ", " / ")


def split_primary_player(name_text: str, primary_player: str) -> tuple[str, str]:
    """If primary_player is found inside name_text, return
    (primary_player, leftover_text_with_it_removed). If primary_player
    is blank or not found, return (name_text, "") unchanged.

    primary_player is normalized (stripped, internal whitespace
    collapsed) before searching. This matters because BSC's raw Name
    field often has NO space before the leftover text at all - e.g.
    "Michael Jordan1985 NBA ROY 1995" - so any stray leading/trailing
    or doubled whitespace on the typed-in primary_player (easy to
    introduce via voice-to-text, or a stale value carried over from
    "reuse settings") breaks the exact substring match completely and
    dumps the ENTIRE raw name through unsplit, which is worse than
    useless. Confirmed 2026-07-24 (Brandon) against exactly this
    pattern - a trailing space on "Michael Jordan " failed to match
    "Michael Jordan1985..." even though the name is clearly present.
    """
    if not primary_player:
        return name_text, ""
    primary_player = WHITESPACE_PATTERN.sub(" ", primary_player).strip()
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

    # Lettered card numbers (e.g. "1b", "1c") are variants of the same
    # base card. Strip the letter so they group with the base card (#1)
    # in merge. The letter suffix is captured in is_letter_variant so
    # the merge step knows to build a parallel from the description.
    letter_match = LETTER_VARIANT_PATTERN.match(card_number)
    is_letter_variant = bool(letter_match)
    if letter_match:
        card_number = letter_match.group(1)  # "1b" -> "1"

    primary_player = context.get("primary_player", "")
    player, leftover_name_text = split_primary_player(record.name, primary_player)
    player = split_concatenated_names(player)

    variant_name, fallback_serial = clean_variant_name(record)

    raw_team = record.team.strip() if record.team and record.team.strip() else context.get("team", "")
    team = normalize_team_separators(raw_team)

    occurrence = RawOccurrence(
        type=context.get("type", ""),
        sport=context.get("sport", ""),
        year=year,
        brand=brand,
        set=set_value,
        card_number=card_number,
        card_number_prefix=card_number_prefix,
        player=player,
        team=team,
        section=context.get("section", ""),
        variant_name=variant_name,
        attributes=record.attributes,
        leftover_name_text=leftover_name_text,
        is_base=(record.variant.strip().lower() == "base"),
        is_insert=(record.variant.strip().lower() == "insert"),
        is_letter_variant=is_letter_variant,
        description=record.description,
    )
    return occurrence, fallback_serial


def convert_all(records: list[CardRecord], context: dict | None = None) -> list[tuple[RawOccurrence, str]]:
    return [build_raw_occurrence(r, context) for r in records]
