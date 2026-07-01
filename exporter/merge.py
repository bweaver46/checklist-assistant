"""
Phase 6: group raw occurrences by card identity, compute each card's
scalar Insert (the text common to all its print versions) and Sub_Type,
and build the per-print-version Parallel/Serial list.

Insert/Parallel logic (per Brandon, 2026-06-29), using the real Anime
example - one card_number, four website rows:
    Variant Name: "Anime", "Anime Black Refractors",
                  "Anime Red Refractors", "Anime SuperFractors"

"Anime" is common to all four -> Insert = "Anime". What's left over per
row is the Parallel: "" (the plain Anime row - this is the base
printing, contributes no parallel), "Black Refractor", "Red Refractor",
"SuperFractor" (Refractors/SuperFractors normalized to singular, but
NOT dropped - it's the actual distinguishing word here).

A row contributes a parallel_N/serial_N slot only if it has a non-blank
leftover (after removing the common Insert text) OR a serial number
(SN/PR) of its own. The plain "Anime" row has neither, so it
contributes nothing - no blank slot, indexing starts directly at
parallel_1 with "Black Refractor". If that base row DID have a serial
(e.g. SN50 with no name), it would get its own slot: parallel blank,
serial filled in.

card_number's prefix (e.g. "T91-") is prepended to the front of Insert,
not to each parallel - it identifies the subset/era the whole card
belongs to, not any one print version of it.
"""

from __future__ import annotations

import re
from collections import OrderedDict

from exporter.checklist_template import ChecklistRow
from exporter.convert import RawOccurrence, normalize_plural_terms, parse_serial, AUTOGRAPH_PATTERN

WHITESPACE_PATTERN = re.compile(r"\s+")


def longest_common_word_prefix(texts: list[str]) -> str:
    """Word-wise common leading prefix across all non-empty texts,
    case-insensitive comparison, original casing preserved in output.
    Empty list or all-blank input -> "". A single non-empty text ->
    that whole text (its own full word list trivially matches itself)."""
    non_empty = [t for t in texts if t and t.strip()]
    if not non_empty:
        return ""

    word_lists = [t.split() for t in non_empty]
    shortest_len = min(len(w) for w in word_lists)

    common_words = []
    for i in range(shortest_len):
        candidate = word_lists[0][i]
        if all(words[i].lower() == candidate.lower() for words in word_lists):
            common_words.append(candidate)
        else:
            break

    return " ".join(common_words)


def strip_common_prefix(text: str, prefix: str) -> str:
    """Remove `prefix`'s words from the front of `text`, word-wise,
    case-insensitive. If text doesn't actually start with prefix
    (shouldn't normally happen), text is returned unchanged."""
    if not text:
        return ""
    if not prefix:
        return text

    text_words = text.split()
    prefix_words = prefix.split()
    if len(text_words) < len(prefix_words):
        return text

    head = [w.lower() for w in text_words[: len(prefix_words)]]
    if head != [w.lower() for w in prefix_words]:
        return text

    return " ".join(text_words[len(prefix_words):])


def group_key(occurrence: RawOccurrence) -> tuple:
    return (
        occurrence.type,
        occurrence.sport,
        occurrence.year,
        occurrence.brand,
        occurrence.set,
        occurrence.card_number,
        occurrence.player,
        occurrence.team,
    )


def build_checklist_rows(
    occurrences_with_fallback: list[tuple[RawOccurrence, str]]
) -> list[ChecklistRow]:
    groups: "OrderedDict[tuple, list[tuple[RawOccurrence, str]]]" = OrderedDict()
    for occurrence, fallback_serial in occurrences_with_fallback:
        groups.setdefault(group_key(occurrence), []).append((occurrence, fallback_serial))

    rows: list[ChecklistRow] = []

    for key, group in groups.items():
        type_, sport, year, brand, set_value, card_number, player, team = key
        first_occurrence = group[0][0]

        # Base rows (is_base=True) are excluded from the common-prefix
        # calculation entirely - their blank variant_name would corrupt
        # the Insert prefix for the rest of the group, and their serial
        # goes into base_serial, not the parallels list.
        non_base_group = [(occ, fb) for occ, fb in group if not occ.is_base]
        has_base_rows = len(non_base_group) < len(group)
        variant_texts = [occ.variant_name for occ, _ in non_base_group]

        # When base rows are present, the non-base rows are parallels OF
        # the base card. A single non-base text should be a parallel, not
        # the Insert - only derive a common Insert prefix when 2+ non-base
        # rows share one. (The single-item-is-its-own-prefix behavior is
        # intentional for Insert-only groups with one print version, not
        # for base+parallel groups.)
        if has_base_rows and len(non_base_group) <= 1:
            common_prefix = ""
        else:
            common_prefix = longest_common_word_prefix(variant_texts)

        card_number_prefix = first_occurrence.card_number_prefix
        insert = normalize_plural_terms(common_prefix)
        if card_number_prefix:
            insert = f"{card_number_prefix} {insert}".strip()
        insert = WHITESPACE_PATTERN.sub(" ", insert).strip()

        section = first_occurrence.section
        leftover_texts = [
            occ.leftover_name_text for occ, _ in group if occ.leftover_name_text.strip()
        ]
        has_autograph = any(
            occ.attributes and occ.attributes != "-" and AUTOGRAPH_PATTERN.search(occ.attributes)
            for occ, _ in group
        )

        card_attrs_parts = []
        if section.strip():
            card_attrs_parts.append(section.strip())
        for leftover in leftover_texts:
            if leftover.strip() and leftover.strip() not in card_attrs_parts:
                card_attrs_parts.append(leftover.strip())

        already_says_autograph = any(
            "autograph" in (text or "").lower()
            for text in [set_value, insert, section] + leftover_texts
        )
        if has_autograph and not already_says_autograph:
            card_attrs_parts.append("Autograph")
        card_attrs = ", ".join(card_attrs_parts)

        parallels: list[tuple[str, str]] = []
        for occ, fallback_serial in non_base_group:
            remainder = strip_common_prefix(occ.variant_name, common_prefix)
            remainder = normalize_plural_terms(remainder)
            serial = parse_serial(occ.attributes) or fallback_serial

            if not remainder.strip() and not serial:
                continue  # nothing to record for this print version

            parallels.append((remainder, serial))

        # base_serial: if any row in this group was a Base row and had a
        # serial (SN/PR), capture it here. base itself is always blank
        # from the parser - filled manually after export when needed.
        base_serial = ""
        for occ, fallback_serial in group:
            if occ.is_base:
                base_serial = parse_serial(occ.attributes) or fallback_serial
                break  # at most one base row per card group

        rows.append(
            ChecklistRow(
                type=type_,
                sub_type=sport,       # sport value goes into sub_type column
                year=year,
                brand=brand,
                set=set_value,
                insert=insert,
                attributes=card_attrs,  # was sub_type
                card_number=card_number,
                player=player,
                team=team,
                base="",
                base_serial=base_serial,
                parallels=parallels,
            )
        )

    return rows
