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
from dataclasses import replace

from exporter.checklist_template import ChecklistRow
from exporter.convert import RawOccurrence, normalize_plural_terms, parse_serial, AUTOGRAPH_PATTERN

WHITESPACE_PATTERN = re.compile(r"\s+")

# Prefixes like "VAR: " or "SP: " that BSC prepends to description text.
DESCRIPTION_PREFIX_PATTERN = re.compile(r'^[A-Z]+:\s*')


def clean_description(description: str) -> str:
    """Clean a BSC Add-page description into a usable parallel name.

    'VAR: Dancing Dodgers Variation' -> 'Dancing Dodgers'
    'SP: Short Print'                -> 'Short Print'

    Rules:
    - Strip any leading 'XXX: ' prefix (the abbreviation BSC uses to
      classify the description type - we don't need it)
    - Strip trailing ' Variation' (redundant - the whole point of a
      parallel slot is that it IS a variation)
    - Collapse whitespace
    """
    if not description:
        return ""
    text = DESCRIPTION_PREFIX_PATTERN.sub("", description)
    if text.lower().endswith(" variation"):
        text = text[:-len(" variation")]
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def tokenize_attributes(attrs: str) -> set[str]:
    """Split a raw BSC Attribute(s) cell ('AS, SP, VAR', '-', 'SN150')
    into the individual non-serial, non-VAR tokens it actually carries
    ('AS', 'SP'). VAR is dropped (implied by being a parallel); serial
    numbers (SN/PR) are dropped (handled separately via parse_serial)."""
    if not attrs or attrs.strip() == "-":
        return set()
    return {
        t.strip()
        for t in attrs.split(",")
        if t.strip() and t.strip().upper() != "VAR"
        and not re.match(r'^(SN|PR)\d+$', t.strip(), re.IGNORECASE)
    }


def attributes_extra(variant_attrs: str, base_attrs: str) -> str:
    """Return the attribute tokens present in variant_attrs but NOT in
    base_attrs, excluding 'VAR' (which is implied by being a parallel).

    'SP, VAR' vs '-'  -> 'SP'
    'SN50'    vs '-'  -> ''   (serials are handled via parse_serial)
    'SP'      vs 'SP' -> ''   (same as base, goes to card attributes)
    """
    base_tokens = tokenize_attributes(base_attrs)
    variant_tokens = tokenize_attributes(variant_attrs)
    extra = variant_tokens - base_tokens
    return ", ".join(sorted(extra))


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


def prelim_key(occurrence: RawOccurrence) -> tuple:
    """Key used to bucket raw occurrences before insert-cluster splitting
    (see assign_insert_clusters). Does NOT by itself guarantee one card -
    see that function for why."""
    return (
        occurrence.type,
        occurrence.sport,
        occurrence.year,
        occurrence.brand,
        occurrence.set,
        occurrence.card_number,
        normalize_player_for_grouping(occurrence.player),
    )


def assign_insert_clusters(bucket: list[tuple[RawOccurrence, str]]) -> list[int]:
    """A (card_number, player) bucket can legitimately contain more than
    one unrelated card. BSC assigns each Insert set its own 1-N
    numbering, and those numbering schemes collide across different
    inserts for the same player - e.g. 2026 Donruss Jonah Tong's "#12" is
    BOTH the "Crunch Time" insert AND a completely separate "Diamond
    Marvels" insert (confirmed against the raw export, Brandon
    2026-08-06). Grouping on card_number+player alone merged both
    inserts' full run of parallels into one row with a blank Insert
    (no shared word-prefix between "Crunch Time..." and "Diamond
    Marvels..." texts) and every print version of both dumped as flat
    Parallels instead.

    Every Base and Parallel row in a bucket always belongs to that one
    base card - cluster 0, never split (Optic colors, Rated Prospects
    Optic Signatures colors, etc. all legitimately belong to the one
    base card they're rows for).

    Insert rows are different: a card's OWN number can independently
    double as the number BSC gave an entirely unrelated Insert set for
    that same player - e.g. 2026 Donruss Jacob Wilson is base card
    #13 (with its own normal Optic/Artist Proofs parallels), and #13
    is SEPARATELY the number his "Diamond Marvels" insert happens to
    use (confirmed against the raw export, Brandon 2026-08-06 - the
    first version of this fix assumed a Base row in the bucket meant
    everything else was that card's own parallel, which merged Diamond
    Marvels into Jacob Wilson's base row instead of splitting it out).
    So only Insert-type rows (RawOccurrence.is_insert) get clustered:
    walk them in the order BSC listed them and start a new cluster
    whenever a row's Variant Name doesn't share at least a two-word
    prefix with the current cluster's running anchor - i.e. whenever
    the listing has visibly moved on to a different insert. A bucket
    can freely mix cluster 0 (Base + its Parallels) with one or more
    Insert clusters found this way.

    The anchor is the SHARED prefix seen so far in the current cluster,
    not just the first row's full text - it shrinks as more of the
    insert's differently-suffixed print versions come in. This matters
    for inserts that never print a bare, un-suffixed version at all -
    e.g. 2020 Panini Diamond Kings' "DK 206 Signatures" insert only
    ever appears as "DK 206 Signatures Holo Blue", "...Holo Gold",
    "...Masterpiece", etc. (confirmed against the raw export, Brandon
    2026-08-08). Comparing every row against a fixed first-row anchor
    ("...Holo Blue") meant "...Holo Gold" didn't literally start with
    those exact words and got treated as an unrelated new insert, and
    so on for every remaining row - the whole insert fragmented into
    one cluster per parallel instead of staying one card. Shrinking the
    anchor to the ACTUAL shared prefix after each row ("DK 206
    Signatures", once "Holo Blue" and "Holo Gold" disagree at word 4)
    fixes this without needing every insert to have a plain row to
    anchor off of.

    A minimum of two shared words is required to CONTINUE a cluster
    once the anchor has already had to shrink to match a prior row -
    a single generic shared word surviving a shrink (e.g. two unrelated
    inserts that both merely start with "Rookie") isn't a strong enough
    signal on its own, and would risk merging genuinely different
    inserts the same way this function exists to prevent. That
    threshold does NOT apply when a row fully extends the anchor as-is
    (no shrinking needed) - otherwise a genuinely one-word insert name
    (e.g. "Anime", extended by "Anime Black Refractors") would
    incorrectly fragment on its very first color variant, since the
    bare anchor itself is only one word.

    A card_number of literally "NNO" (BSC's own placeholder for "this
    print doesn't have a number on it at all") gets the same treatment
    as an Insert-type row, even when BSC labeled it "Parallel" - unlike
    a real numbered Parallel row (which conceptually parallels some
    base card, even one BSC didn't separately list for this specific
    player), "NNO" never appears as a genuine Base row for ANYONE in a
    product, so there's no base card being paralleled at all. Confirmed
    against Brandon's raw export, 2026-08-15 (2025 Topps Allen &
    Ginter): 350 different players' "Mini No Number"/"Framed Mini
    Cloth" Parallel rows were all silently folding into the base-set
    count (no Insert, no Base row of their own - just a nameless entry
    with one parallel attached), inflating what looked like a 350-card
    base checklist to 709 "base" rows and making Brandon's real,
    correctly-sized numbered base set impossible to see clearly.
    """
    is_no_number_placeholder = bucket[0][0].card_number.strip().upper() == "NNO" if bucket else False
    cluster_ids: list[int] = []
    anchor: str = ""
    current_id = 0
    next_id = 1
    for occ, _ in bucket:
        if occ.is_base or (not occ.is_insert and not is_no_number_placeholder):
            cluster_ids.append(0)
            continue
        text = occ.variant_name
        shared = longest_common_word_prefix([anchor, text]) if anchor else ""
        is_full_extension = bool(shared) and shared.lower() == anchor.lower()
        if not shared or (not is_full_extension and len(shared.split()) < 2):
            anchor = text
            current_id = next_id
            next_id += 1
        else:
            anchor = shared
        cluster_ids.append(current_id)
    return cluster_ids


# Known trailing subset/insert abbreviation codes BSC appends directly onto
# the Name cell text itself (not the separate Attribute(s) column) for some
# rows of a card but not others - e.g. the same physical "World Series
# Highlights" card_number showed up scraped as ALL of "World Series
# Highlights", "World Series Highlights WSHL", "World Series Highlights
# WSHL,", and "World Series Highlights SP, WSHL," across its different
# print-version rows (Brandon, 2026-08-02, 2026 Topps Heritage). Because
# group_key previously matched on the raw player text verbatim, each of
# these variations formed its own separate output row instead of being
# recognized as parallels of the same card. Extend this set as new codes
# turn up in other sets - same "grows over time" spirit as
# settings/brand_set_exceptions.csv in the sibling PSA import project.
KNOWN_TRAILING_NAME_CODES = {"LL", "ALC", "NLC", "WSHL", "SP"}


def normalize_player_for_grouping(player: str) -> str:
    """Strip a trailing comma and/or a trailing run of known subset codes
    (see KNOWN_TRAILING_NAME_CODES), and a trailing period right after a
    generational suffix (Jr/Sr/II/III/IV), so different scrapes of the
    same card that got these things inconsistently attached to the Name
    text still group together. The period case is real, not
    hypothetical: 2025 Topps Allen & Ginter #123 scraped as both "Bobby
    Witt Jr." and "Bobby Witt Jr" across different parallel rows of the
    exact same card - split into two separate rows in the export instead
    of staying one card with all its parallels (confirmed against
    Brandon's real raw export cross-checked against his existing ColLock
    library data for the same product, 2026-08-16 - ColLock's own copy
    correctly shows this as one unified card). Only ever used for the
    grouping KEY - the actual displayed player text is chosen separately
    (see pick_display_player below) so nothing is lost from the export,
    just consolidated onto one row."""
    text = player.strip()
    while True:
        text = text.rstrip(",").rstrip()
        words = text.split(" ")
        if words and words[-1] in KNOWN_TRAILING_NAME_CODES:
            text = " ".join(words[:-1]).rstrip()
            continue
        if words and re.match(r"^(Jr|Sr|I{2,3}|IV)\.$", words[-1], re.IGNORECASE):
            text = " ".join(words[:-1] + [words[-1][:-1]])
            continue
        break
    return text


def pick_display_player(group: list[tuple]) -> str:
    """Prefer a raw text ending in a period-suffixed generational marker
    (Jr./Sr./II./III./IV.) over one missing the period, since that's the
    more standard display form (confirmed against Brandon's existing
    ColLock library data for this same product, which displays it that
    way) - both forms group onto the same row via
    normalize_player_for_grouping, this just picks the nicer one to
    actually show. Otherwise, prefer whichever occurrence's raw player
    text is already 'clean' (equal to its own normalized form - no
    trailing comma, no known trailing code) as what actually gets
    exported, since that's the version without scrape-artifact suffix
    text stuck on it. Falls back to the first occurrence's raw text if
    nothing else matches."""
    for occ, _ in group:
        raw = occ.player.strip()
        words = raw.split(" ")
        if words and re.match(r"^(Jr|Sr|I{2,3}|IV)\.$", words[-1], re.IGNORECASE):
            return raw
    for occ, _ in group:
        raw = occ.player.strip()
        if raw == normalize_player_for_grouping(raw):
            return raw
    return group[0][0].player


def pick_display_team(group: list[tuple]) -> str:
    """Prefer the first non-blank team text in the group - a blank team
    on one row of an otherwise-identical card is a scrape gap (the Add
    page fetch didn't return one that time), not a genuinely different
    card, so it shouldn't produce its own row nor should it win out over
    a row where the team WAS captured."""
    for occ, _ in group:
        if occ.team.strip():
            return occ.team.strip()
    return ""


def remap_placeholder_numbers_to_real_base_card(
    occurrences_with_fallback: list[tuple[RawOccurrence, str]]
) -> list[tuple[RawOccurrence, str]]:
    """A row with card_number "NNO" (BSC's placeholder for "no number
    printed on this card") is usually still the SAME player's real,
    already-numbered base card - just a parallel print of it that
    happens to lack a number, mis-keyed under "NNO" instead of that
    card's actual number. Confirmed against Brandon's real raw export,
    2026-08-16 (2025 Topps Allen & Ginter): 349 of 350 "NNO" players
    also have a genuine numbered Base row elsewhere in the same product
    - e.g. Ivan Rodriguez is base card #309, and his "Mini No Number"
    parallel is scraped as card_number "#NNO" instead of "#309", even
    though it's clearly his own card's parallel (same player, same
    team, same product). Brandon: "NNO should show up in the base set
    right?" - yes, and this is why: it almost always already IS part of
    that player's base card, just mis-numbered by BSC.

    Rewrites card_number on any "NNO" occurrence to that player's real
    Base card_number, so it lands in the SAME group as the rest of
    their card during normal clustering, instead of being treated as
    its own separate identity (the earlier, less correct fix - commit
    9bd7c90 - promoted "NNO" itself to be the card's insert name for
    EVERY such row, which solved the base-count inflation but at the
    cost of pulling every one of these away from the card they actually
    belong to).

    Only remaps within the SAME product (type/sport/year/brand/set) and
    the SAME player (via normalize_player_for_grouping, so e.g. a
    trailing-period Jr./Sr. difference doesn't block the match) - never
    across different products or players. A player with genuinely NO
    real Base row anywhere (e.g. this file's one exception, Yu Darvish)
    is left with "NNO" as their card_number, which still gets the
    dedicated placeholder handling in assign_insert_clusters/
    build_checklist_rows below."""
    real_base_numbers: dict[tuple, str] = {}
    for occ, _ in occurrences_with_fallback:
        if occ.is_base and occ.card_number.strip().upper() != "NNO":
            product_player_key = (
                occ.type, occ.sport, occ.year, occ.brand, occ.set,
                normalize_player_for_grouping(occ.player),
            )
            real_base_numbers.setdefault(product_player_key, occ.card_number)

    remapped: list[tuple[RawOccurrence, str]] = []
    for occ, fallback_serial in occurrences_with_fallback:
        if occ.card_number.strip().upper() == "NNO":
            product_player_key = (
                occ.type, occ.sport, occ.year, occ.brand, occ.set,
                normalize_player_for_grouping(occ.player),
            )
            real_number = real_base_numbers.get(product_player_key)
            if real_number:
                occ = replace(occ, card_number=real_number)
        remapped.append((occ, fallback_serial))
    return remapped


def build_checklist_rows(
    occurrences_with_fallback: list[tuple[RawOccurrence, str]]
) -> list[ChecklistRow]:
    occurrences_with_fallback = remap_placeholder_numbers_to_real_base_card(
        occurrences_with_fallback
    )
    prelim: "OrderedDict[tuple, list[tuple[RawOccurrence, str]]]" = OrderedDict()
    for occurrence, fallback_serial in occurrences_with_fallback:
        prelim.setdefault(prelim_key(occurrence), []).append((occurrence, fallback_serial))

    groups: "OrderedDict[tuple, list[tuple[RawOccurrence, str]]]" = OrderedDict()
    for key, bucket in prelim.items():
        cluster_ids = assign_insert_clusters(bucket)
        for (occ, fallback_serial), cluster_id in zip(bucket, cluster_ids):
            groups.setdefault(key + (cluster_id,), []).append((occ, fallback_serial))

    rows: list[ChecklistRow] = []

    for key, group in groups.items():
        type_, sport, year, brand, set_value, card_number, _normalized_player, _cluster_id = key
        player = pick_display_player(group)
        team = pick_display_team(group)
        first_occurrence = group[0][0]

        # Base rows (is_base=True) are excluded from the common-prefix
        # calculation entirely - UNLESS they are lettered variants (1b, 1c),
        # which BSC marks as "Base" even though they are really parallels.
        non_base_group = [
            (occ, fb) for occ, fb in group
            if not occ.is_base or occ.is_letter_variant
        ]
        has_base_rows = len(non_base_group) < len(group)
        variant_texts = [occ.variant_name for occ, _ in non_base_group]

        # A single non-base row should become a Parallel, not the Insert,
        # UNLESS the site itself labeled that row "Insert" (occ.is_insert) -
        # that's the actual signal for "this text names the card itself,
        # not a variation of some other base printing", not whether a
        # Base row happened to also be captured in this bucket.
        #
        # Using has_base_rows here (previous version) was wrong: many
        # autograph/relic parallels (e.g. "#SG-CO", "#SSS-AR") have no
        # separate plain Base printing at all - BSC lists exactly one row
        # for them, typed "Parallel" - so has_base_rows was False for
        # them even though they are unambiguously NOT their own Insert.
        # That silently dumped the whole Parallel name into `insert`
        # instead of `parallel_1` (Brandon, 2026-08-06 - Topps Chrome
        # export, ~64 cards mis-tagged this way in one run).
        #
        # (The single-item-is-its-own-prefix behavior is still correct
        # and intentional for a real Insert-only group with one print
        # version - that's exactly what occ.is_insert=True means.)
        if len(non_base_group) <= 1:
            single_is_insert = bool(non_base_group) and (
                non_base_group[0][0].is_insert or card_number.strip().upper() == "NNO"
            )
            common_prefix = variant_texts[0] if single_is_insert else ""
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
        # Find the base (non-lettered, non-base-variant) row's attributes.
        # Needed here (not just for the lettered-variant comparison further
        # down) because this is also where a plain code like "AS" or "RC" -
        # scraped straight off BSC's own Attribute(s) column, with no
        # serial number and no Add-page description text behind it -
        # actually makes it into the output. Confirmed missing entirely
        # (Brandon, 2026-08-01, 2026 Topps Heritage #10 "AS", #13 "ASR",
        # #32 "RC"): these tokens were previously read into occ.attributes
        # but only ever consulted for autograph detection and the lettered-
        # variant's attributes_extra() delta - never copied into card_attrs
        # itself, so a code with no other distinguishing text just vanished.
        base_occ_attrs = "-"
        for occ, _ in group:
            if occ.is_base and not occ.is_letter_variant:
                base_occ_attrs = occ.attributes
                break
        else:
            # No Base row in this group at all. If the group is a single
            # occurrence (no parallel siblings at all - the card IS this
            # one row), treat ITS attributes the same way a real base
            # row's would be used below, so a code like "MEM" on a
            # single-print Insert card doesn't just vanish (Brandon,
            # 2026-08-15: 2025 Topps Allen & Ginter "Relics No Number
            # Back" - MEM/SN25 on the one and only row for that insert -
            # confirmed against his raw export). Scoped to len<=1 only -
            # a bare row that DOES have real parallel siblings (e.g. an
            # "Anime" base print alongside "Anime Black Refractors") is a
            # different, already-covered case (see bare_occurrence_serial
            # below and test_base_row_with_only_a_serial_gets_blank_
            # parallel_with_serial) and keeps its existing behavior.
            if len(non_base_group) <= 1:
                for occ, _ in non_base_group:
                    if not strip_common_prefix(occ.variant_name, common_prefix).strip():
                        base_occ_attrs = occ.attributes
                        break

        # Autograph detection must come from the card's OWN print version,
        # not from whichever of its parallels happens to be autographed.
        # A group WITH a base row has one plain, non-autographed printing
        # (the base row itself) even when one of its parallels is an
        # autograph version - e.g. 2026 Donruss #101 Konnor Griffin is a
        # plain Rated Prospect; only its "Rated Prospects Optic Signatures"
        # PARALLEL is autographed. Checking the whole group here previously
        # tagged the base card itself as "Autograph" (Brandon, 2026-08-06).
        # A group with NO base row (a pure-Insert card, already isolated to
        # its own insert by assign_insert_clusters above) has no such
        # distinction to make - any row in it carrying AU means the card
        # itself is an autograph insert.
        if has_base_rows:
            has_autograph = bool(
                base_occ_attrs and base_occ_attrs != "-" and AUTOGRAPH_PATTERN.search(base_occ_attrs)
            )
        else:
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
        for token in sorted(tokenize_attributes(base_occ_attrs)):
            # AU is always represented via has_autograph -> "Autograph"
            # text below (or correctly omitted as redundant) - including
            # it here too would double it up ("AU, Autograph").
            if AUTOGRAPH_PATTERN.match(token):
                continue
            if token not in card_attrs_parts:
                card_attrs_parts.append(token)

        already_says_autograph = any(
            "autograph" in (text or "").lower()
            for text in [set_value, insert, section] + leftover_texts
        )
        if has_autograph and not already_says_autograph:
            card_attrs_parts.append("Autograph")
        card_attrs = ", ".join(card_attrs_parts)

        # Separate lettered variants (1b, 1c) from regular non-base rows.
        # Lettered variants always build their parallel from the description
        # fetched from the Add page, not from the variant_name prefix logic.
        letter_group = [(occ, fb) for occ, fb in non_base_group if occ.is_letter_variant]
        regular_group = [(occ, fb) for occ, fb in non_base_group if not occ.is_letter_variant]


        parallels: list[tuple[str, str]] = []
        bare_occurrence_serial = ""

        # Regular (non-lettered) parallels via the existing prefix logic.
        for occ, fallback_serial in regular_group:
            remainder = strip_common_prefix(occ.variant_name, common_prefix)
            remainder = normalize_plural_terms(remainder)
            serial = parse_serial(occ.attributes) or fallback_serial

            if not remainder.strip() and not serial:
                continue

            if not remainder.strip() and len(non_base_group) <= 1:
                # This is the ONLY occurrence in the whole group (no
                # parallel siblings at all - not even an un-named one) -
                # its whole variant_name text WAS the common prefix
                # (insert name), so this isn't a separately-named
                # parallel, it's the card's own bare printing. Its serial
                # belongs on the card itself (base_serial), not floating
                # in a blank-named parallel slot ("", "25") that reads
                # like a broken row (2025 Topps Allen & Ginter "Relics No
                # Number Back" - a single-occurrence Insert card, MEM/
                # SN25 on the one and only row - confirmed against
                # Brandon's raw export, 2026-08-15).
                #
                # Scoped to len<=1 ONLY - a bare row that DOES have real
                # parallel siblings (e.g. an "Anime" base print alongside
                # "Anime Black Refractors") keeps its existing blank-
                # parallel-with-serial behavior instead (see
                # test_base_row_with_only_a_serial_gets_blank_parallel_
                # with_serial) - that pattern represents a real, specific
                # print version sitting alongside its named siblings, not
                # an orphaned row with nothing else on the card at all.
                if not bare_occurrence_serial:
                    bare_occurrence_serial = serial
                continue

            parallels.append((remainder, serial))

        # Lettered variant parallels built from Add-page description.
        for occ, fallback_serial in letter_group:
            desc = clean_description(occ.description)
            extra_attrs = attributes_extra(occ.attributes, base_occ_attrs)
            parallel_name = f"{extra_attrs} {desc}".strip() if extra_attrs else desc
            serial = parse_serial(occ.attributes) or fallback_serial
            parallels.append((parallel_name, serial))

        # base_serial: if any row in this group was a Base row and had a
        # serial (SN/PR), capture it here. base itself is always blank
        # from the parser - filled manually after export when needed.
        # Falls back to bare_occurrence_serial (above) for a group with
        # no Base row at all, so a single-occurrence Insert card's own
        # serial still ends up somewhere sensible instead of a blank-
        # named parallel.
        base_serial = ""
        for occ, fallback_serial in group:
            if occ.is_base and not occ.is_letter_variant:
                base_serial = parse_serial(occ.attributes) or fallback_serial
                break
        if not base_serial:
            base_serial = bare_occurrence_serial

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
