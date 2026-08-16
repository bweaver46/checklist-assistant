"""
Tests for the exporter pipeline (Phases 5-7), using fake CardRecords
shaped like real BuySportsCards rows. Reflects the model finalized
2026-06-29: Insert and Sub_Type are SCALAR (one per card, computed from
everything common across that card's print versions); only
Parallel/Serial repeat per print version.

Key real example driving this design - one card_number (#BA-23), four
website rows:
    "Anime", "Anime Black Refractors", "Anime Red Refractors",
    "Anime SuperFractors"
-> Insert = "Anime" (the common part).
-> Parallels: (none for plain "Anime" - it's the base printing),
   "Black Refractor", "Red Refractor", "SuperFractor" (singularized,
   NOT dropped - the earlier "drop redundant Refractor" rule was wrong
   and has been removed).
"""

from scraper.card_record import CardRecord
from exporter.convert import (
    convert_all, parse_set, parse_serial, split_trailing_slash_serial,
    clean_card_number, extract_card_number_prefix, split_primary_player,
    normalize_plural_terms, load_brand_set_exceptions,
    split_concatenated_names, normalize_team_separators,
)
from exporter.merge import build_checklist_rows, longest_common_word_prefix, strip_common_prefix, clean_description, attributes_extra
from exporter.cleanup import apply_cleanup
from exporter.checklist_template import ChecklistRow
from exporter.final_export import sort_rows_by_brand


def convert_and_build(records, context=None):
    occurrences = convert_all(records, context or {})
    return apply_cleanup(build_checklist_rows(occurrences))


# --- parse_set: brand/set split (Rule 1) ---

def test_parse_set_brand_is_first_word_rest_is_set():
    assert parse_set("2026 Panini Prizm") == ("2026", "Panini", "Prizm")
    assert parse_set("2026 Bowman") == ("2026", "Bowman", "")
    assert parse_set("1991 Topps Baseball") == ("1991", "Topps", "Baseball")
    assert parse_set("") == ("", "", "")


def test_parse_set_brand_exceptions_loaded_from_csv():
    # These come from settings/brand_set_exceptions.csv, editable in
    # Excel/Numbers without touching code. Real cases (2026-06-29):
    # product lines that don't follow the simple first-word-is-brand rule.
    exceptions = load_brand_set_exceptions()
    assert len(exceptions) > 0, "brand_set_exceptions.csv should be loadable"

    assert parse_set("2026 Finest") == ("2026", "Topps", "Finest")
    assert parse_set("2026 Topps Now") == ("2026", "Topps", "Topps Now")
    assert parse_set("2026 Bowman's Best") == ("2026", "Bowman", "Bowman's Best")
    assert parse_set("2026 Stadium Club") == ("2026", "Topps", "Stadium Club")
    assert parse_set("2026 Upper Deck") == ("2026", "Upper Deck", "Upper Deck")
    assert parse_set("2026 UD") == ("2026", "Upper Deck", "Upper Deck")
    assert parse_set("2026 President's Choice") == (
        "2026", "President's Choice", "President's Choice"
    )
    assert parse_set("2026 Lauran Taylor") == ("2026", "Lauran Taylor", "Lauran Taylor")


def test_brand_set_exception_preserves_trailing_words():
    # An exception match must not silently drop words that come AFTER
    # the matched pattern - e.g. "UD Series 1" needs the "Series 1"
    # preserved, not just "Upper Deck" with the rest thrown away.
    assert parse_set("2026 UD Series 1") == ("2026", "Upper Deck", "Upper Deck Series 1")
    assert parse_set("2026 Stadium Club Chrome") == ("2026", "Topps", "Stadium Club Chrome")


# --- parse_serial / PR-as-SN ---

def test_parse_serial():
    assert parse_serial("SN150") == "150"
    assert parse_serial("AU, SN150") == "150"
    assert parse_serial("AU") == ""
    assert parse_serial("-") == ""
    assert parse_serial("PR99") == "99"


def test_trailing_slash_serial_fallback():
    assert split_trailing_slash_serial("Gold /50") == ("Gold", "50")
    assert split_trailing_slash_serial("Anime") == ("Anime", "")


# --- normalize_plural_terms: singularize, never drop ---

def test_normalize_plural_terms_singularizes_without_dropping():
    assert normalize_plural_terms("Black Refractors") == "Black Refractor"
    assert normalize_plural_terms("SuperFractors") == "SuperFractor"
    assert normalize_plural_terms("Silver Prizms") == "Silver Prizm"
    assert normalize_plural_terms("Black-Wave") == "Black Wave"


# --- card_number cleaning / prefix extraction (Rule 2) ---

def test_clean_card_number_strips_hash():
    assert clean_card_number("#T91-1") == "T91-1"
    assert clean_card_number("517") == "517"


def test_extract_card_number_prefix():
    # Prefix extraction is disabled - always blank regardless of input.
    assert extract_card_number_prefix("T91-1") == ""
    assert extract_card_number_prefix("TBC15") == ""
    assert extract_card_number_prefix("517") == ""
    assert extract_card_number_prefix("12P5") == ""
    assert extract_card_number_prefix("O-123") == ""


# --- Primary Player splitting (Rule 3) ---

def test_split_primary_player_extracts_name_and_leftover():
    name, leftover = split_primary_player(
        "Stars Align (Mike TroutZach Neto) CPC", "Mike Trout"
    )
    assert name == "Mike Trout"
    assert leftover == "Stars Align (Zach Neto) CPC"


def test_split_primary_player_not_found_leaves_unchanged():
    name, leftover = split_primary_player("Shohei Ohtani", "Mike Trout")
    assert name == "Shohei Ohtani"
    assert leftover == ""


def test_split_primary_player_handles_trailing_space_on_primary_player():
    # Bug found by Brandon 2026-07-24: a trailing space on the typed-in
    # primary_player used to break the match completely against BSC's
    # raw Name field, which often has NO space before the leftover
    # text (e.g. "Jordan1985..."), dumping the whole raw name through
    # unsplit instead of extracting the player.
    name, leftover = split_primary_player(
        "Michael Jordan1985 NBA ROY 1995", "Michael Jordan "
    )
    assert name == "Michael Jordan"
    assert leftover == "1985 NBA ROY 1995"


def test_split_primary_player_handles_leading_and_doubled_internal_space():
    name, leftover = split_primary_player(
        "Michael Jordan1986-87 3000 Points 1995", "  Michael  Jordan"
    )
    assert name == "Michael Jordan"
    assert leftover == "1986-87 3000 Points 1995"


# --- longest_common_word_prefix / strip_common_prefix ---

def test_longest_common_word_prefix():
    assert longest_common_word_prefix(
        ["Anime", "Anime Black Refractors", "Anime Red Refractors"]
    ) == "Anime"
    assert longest_common_word_prefix(["Only One Variant"]) == "Only One Variant"
    assert longest_common_word_prefix(["", "", ""]) == ""
    assert longest_common_word_prefix(["Totally Different", "Nothing Shared"]) == ""


def test_strip_common_prefix():
    assert strip_common_prefix("Anime Black Refractors", "Anime") == "Black Refractors"
    assert strip_common_prefix("Anime", "Anime") == ""


# --- Full integration: the real Anime example ---

def test_anime_insert_family_full_integration():
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Red Refractors", attributes="SN5"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime SuperFractors", attributes="SN1"),
    ]
    rows = convert_and_build(records)

    assert len(rows) == 1
    row = rows[0]
    assert row.year == "2026"
    assert row.brand == "Bowman"
    assert row.set == ""
    assert row.card_number == "BA-23"
    assert row.insert == "Anime"  # card-number prefix no longer prepended
    assert row.attributes == ""
    # The plain "Anime" row contributes nothing - no blank slot.
    # Indexing starts directly with the first real parallel.
    assert row.parallels == [
        ("Black Refractor", "10"),
        ("Red Refractor", "5"),
        ("SuperFractor", "1"),
    ]


def test_base_row_with_only_a_serial_gets_blank_parallel_with_serial():
    # A "base" printing (remainder == insert, nothing left over) that
    # DOES have its own serial still gets a slot: parallel blank, serial filled.
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="SN50"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].parallels == [
        ("", "50"),
        ("Black Refractor", "10"),
    ]


def test_plain_base_row_no_serial_no_leftover_produces_no_parallel_at_all():
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Bowman",
                   variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].parallels == []
    assert rows[0].insert == ""


def test_autograph_insert_no_redundant_subtype():
    records = [
        CardRecord(name="Mike Trout", card_number="#PRV-MT", set="2026 Bowman",
                   variant="Insert", variant_name="Rookie and Veteran Autographs Purple",
                   attributes="AU, SN250"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.insert == "Rookie and Veteran Autographs Purple"
    assert row.attributes == ""  # "Autograph" already implied by insert text
    # Single-occurrence card (no parallel siblings at all) - its own
    # serial goes to base_serial, not a blank-named parallel slot that
    # would read like a broken/incomplete row (Brandon, 2026-08-15).
    assert row.parallels == []
    assert row.base_serial == "250"


def test_autograph_gets_subtype_when_not_redundant():
    records = [
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Some Insert", attributes="AU, SN50"),
    ]
    rows = convert_and_build(records)
    assert rows[0].attributes == "Autograph"


def test_card_number_prefix_no_longer_prepended_to_insert():
    # Card number prefixes (e.g. "T91-" from "T91-1") are no longer
    # prepended to Insert - that was producing wrong output (e.g. "O-123"
    # -> "O- Anime"). Insert is now taken purely from variant_name.
    records = [
        CardRecord(name="Mike Trout", card_number="#T91-1", set="1991 Topps Baseball",
                   variant="Insert", variant_name="35th Anniversary (Series One)",
                   attributes="-"),
    ]
    rows = convert_and_build(records, {"team": "Los Angeles Angels"})
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "T91-1"
    assert row.insert == "35th Anniversary (Series One)"
    assert row.team == "Los Angeles Angels"


def test_per_card_fetched_team_overrides_manual_context_team():
    # When Team is fetched per-card (record.team is set), it must win
    # over the manual Team context value typed once for the whole run -
    # that's the whole point of fetching it per-card for multi-team sets.
    records = [
        CardRecord(name="Payton Tolle", card_number="#94", set="2026 Donruss",
                   variant="Parallel", variant_name="Optic Gold Velocity",
                   attributes="SN10", team="Boston Red Sox"),
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Donruss",
                   variant="Base", variant_name="-", attributes="-", team=""),
    ]
    rows = convert_and_build(records, {"team": "Los Angeles Angels"})
    by_player = {r.player: r for r in rows}
    assert by_player["Payton Tolle"].team == "Boston Red Sox"
    # No fetched team for this row -> falls back to the manual context value.
    assert by_player["Mike Trout"].team == "Los Angeles Angels"


def test_primary_player_real_example_integration():
    records = [
        CardRecord(name="Stars Align (Mike TroutZach Neto) CPC", card_number="#517",
                   set="2026 Topps", variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records, {"primary_player": "Mike Trout"})
    assert len(rows) == 1
    row = rows[0]
    assert row.player == "Mike Trout"
    assert row.attributes == "Stars Align (Zach Neto) CPC"


def test_section_records_without_renumbering():
    records = [
        CardRecord(name="Mike Trout", card_number="#351", set="2026 Topps",
                   variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records, {"section": "Series 2"})
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "351"
    assert row.attributes == "Series 2"


def test_sort_rows_by_brand():
    rows = [
        ChecklistRow(brand="Topps", set="Now", card_number="6"),
        ChecklistRow(brand="Bowman", set="", card_number="100"),
        ChecklistRow(brand="Upper Deck", set="Series 1", card_number="1"),
    ]
    sorted_rows = sort_rows_by_brand(rows)
    assert [r.brand for r in sorted_rows] == ["Bowman", "Topps", "Upper Deck"]


def test_different_card_numbers_do_not_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Bowman",
                   variant="Base", variant_name="-", attributes="SN50"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 2


def test_base_serial_populated_when_base_row_has_serial():
    # A Base row with SN/PR should have that serial captured in base_serial.
    # The base column itself is always blank from the parser.
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Topps",
                   variant="Base", variant_name="-", attributes="SN50"),
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Topps",
                   variant="Parallel", variant_name="Gold", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.base == ""
    assert row.base_serial == "50"
    assert row.parallels == [("Gold", "10")]


def test_base_serial_blank_when_base_row_has_no_serial():
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Topps",
                   variant="Base", variant_name="-", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Topps",
                   variant="Parallel", variant_name="Gold", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.base == ""
    assert row.base_serial == ""


def test_base_serial_blank_for_insert_only_card():
    # No Base row in this group at all - base_serial stays blank.
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].base_serial == ""


def test_single_occurrence_insert_card_serial_goes_to_base_serial_not_blank_parallel():
    # 2025 Topps Allen & Ginter "Relics No Number Back" - a single-
    # occurrence Insert card (no parallel siblings at all - BSC lists
    # exactly one row for this exact insert+card_number), MEM/SN25 on
    # that one and only row. Previously the whole variant_name got fully
    # absorbed into `insert`, leaving nothing over for the parallels loop
    # except the serial - which produced a blank-named parallel
    # ("", "25") that read like a broken/incomplete row, and dropped the
    # "MEM" code entirely (Brandon, 2026-08-15, confirmed against his
    # raw export).
    records = [
        CardRecord(name="Hank Aaron", card_number="#1", set="2025 Topps Allen & Ginter",
                   variant="Insert", variant_name="Relics No Number Back",
                   attributes="MEM, SN25", team="Atlanta Braves"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.insert == "Relics No Number Back"
    assert row.parallels == []
    assert row.base_serial == "25"
    assert row.attributes == "MEM"


def test_bare_occurrence_with_real_parallel_siblings_keeps_blank_parallel_behavior():
    # The OTHER side of the same fix: a bare/un-suffixed row that DOES
    # have real, separately-named parallel siblings (unlike the single-
    # occurrence case above) keeps producing a blank-named parallel slot
    # for its own serial - it represents one specific print version
    # sitting alongside its named siblings, not an orphaned row with
    # nothing else on the card. See also
    # test_base_row_with_only_a_serial_gets_blank_parallel_with_serial.
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="SN50"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].parallels == [("", "50"), ("Black Refractor", "10")]
    assert rows[0].base_serial == ""


def test_records_with_no_usable_identity_are_dropped_not_ghost_rows():
    # 2025 Topps Allen & Ginter, confirmed against Brandon's real raw
    # export, 2026-08-15: one raw row entirely blank across every field,
    # plus two more with name="" and card_number="'#" (empty once the
    # leading apostrophe/hash is stripped) - real parallel names ("Mini
    # Cloth", "Wood") but no way to know which player's card they
    # belonged to. These previously survived all the way through as
    # ghost rows in the final export - no card_number, no player,
    # nothing to identify them by. There's no way to recover the missing
    # identity after the fact, so they're dropped entirely rather than
    # grouped into their own nonsense "blank" card. A normal record
    # elsewhere in the same batch is unaffected.
    records = [
        CardRecord(name="", card_number="", set="", variant="", variant_name="",
                   attributes="", team="", description=""),
        CardRecord(name="", card_number="'#", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Mini Cloth", attributes="-"),
        CardRecord(name="", card_number="'#", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Wood", attributes="-"),
        CardRecord(name="Hank Aaron", card_number="#13", set="2025 Topps Allen & Ginter",
                   variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].player == "Hank Aaron"


def test_nno_row_remaps_onto_players_real_base_card_when_one_exists():
    # The primary case, added after Brandon asked "NNO should show up
    # in the base set right?" (2026-08-16): a card_number of "NNO" is
    # usually still the SAME player's real, already-numbered base card
    # - just a parallel print of it that happens to lack a number,
    # mis-keyed under "NNO" instead of that card's actual number.
    # Confirmed against Brandon's real raw export: 349 of 350 "NNO"
    # players in 2025 Topps Allen & Ginter also have a genuine numbered
    # Base row elsewhere in the same product - e.g. Ivan Rodriguez is
    # base card #309, and his "Mini No Number" parallel is scraped as
    # card_number "#NNO" instead of "#309", even though it's clearly
    # his own card's parallel (same player, same team, same product).
    # The earlier fix (commit 9bd7c90, test below) promoted "NNO" itself
    # to be the card's insert name for EVERY such row - correct for a
    # player with no real base card, but wrong here: it pulled the
    # parallel away from the card it actually belongs to.
    records = [
        CardRecord(name="Ivan Rodriguez", card_number="#309", set="2025 Topps Allen & Ginter",
                   variant="Base", variant_name="-", attributes="-", team="Florida Marlins"),
        CardRecord(name="Ivan Rodriguez", card_number="#309", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Foil Filagree Gold", attributes="SN50",
                   team="Florida Marlins"),
        CardRecord(name="Ivan Rodriguez", card_number="#NNO", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Mini No Number", attributes="PR50",
                   team="Florida Marlins"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "309"
    assert row.insert == ""
    assert ("Mini No Number", "50") in row.parallels
    assert ("Foil Filagree Gold", "50") in row.parallels


def test_nno_placeholder_parallel_rows_treated_as_their_own_card_not_base():
    # The fallback case: a player with NO real Base row anywhere in the
    # product (e.g. this file's one exception among 350, Yu Darvish) -
    # "NNO" (no number officially) never appears as a genuine Base row
    # for such a player, unlike a normal numbered Parallel row, so
    # there's no base card to re-key this onto. 2025 Topps Allen &
    # Ginter, confirmed against Brandon's real raw export, 2026-08-15:
    # before EITHER fix, 350 different players' "Mini No Number"/"Framed
    # Mini Cloth" Parallel-type rows were silently folding into the
    # base-set count - inflating what should have been roughly a
    # 350-card base checklist to 709 rows tagged as base, and making the
    # real numbered base set impossible to see clearly ("the main set
    # has 709 cards, that cant be correct").
    records = [
        CardRecord(name="Hank Aaron", card_number="#NNO", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Mini No Number", attributes="PR50",
                   team="Atlanta Braves"),
        CardRecord(name="Hank Aaron", card_number="#NNO", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Framed Mini Cloth", attributes="SN10",
                   team="Atlanta Braves"),
    ]
    rows = convert_and_build(records)
    # Two unrelated parallel names sharing no common prefix - two
    # separate cards, same as any other genuinely different inserts
    # colliding on one number (e.g. Crunch Time vs Diamond Marvels).
    assert len(rows) == 2
    inserts = {r.insert for r in rows}
    assert inserts == {"Mini No Number", "Framed Mini Cloth"}
    for row in rows:
        assert row.parallels == []


def test_regular_numbered_parallel_with_no_base_row_still_stays_a_parallel():
    # The other side of the NNO fix: a REAL numbered Parallel row with
    # no Base row scraped for this specific player (e.g. an autograph-
    # only insert card that BSC lists as "Parallel") still stays a
    # parallel of an implied base card, not promoted to its own insert -
    # this is the exact case the single_is_insert gate was built to
    # protect (Brandon, 2026-08-06, Topps Chrome - ~64 cards mis-tagged
    # before that fix). The NNO placeholder check must not weaken this
    # for any real numbered card.
    records = [
        CardRecord(name="Chris Olave", card_number="#SG-CO", set="2026 Topps",
                   variant="Parallel", variant_name="Signature Series Red Laser",
                   attributes="AU, MEM, SN5"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].insert == ""
    assert rows[0].parallels == [("Signature Series Red Laser", "5")]


def test_trailing_period_on_generational_suffix_does_not_split_a_card():
    # 2025 Topps Allen & Ginter #123 scraped as both "Bobby Witt Jr."
    # and "Bobby Witt Jr" across different parallel rows of the exact
    # same card - split into two rows instead of staying one card with
    # all its parallels. Confirmed against Brandon's real raw export,
    # cross-checked against his existing ColLock library data for the
    # same product (2026-08-16) - ColLock's own copy correctly shows
    # this as one unified 39-version card.
    records = [
        CardRecord(name="Bobby Witt Jr.", card_number="#123", set="2025 Topps Allen & Ginter",
                   variant="Base", variant_name="-", attributes="-", team="Kansas City Royals"),
        CardRecord(name="Bobby Witt Jr", card_number="#123", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Daguerreotype", attributes="EXCH",
                   team="Kansas City Royals"),
        CardRecord(name="Bobby Witt Jr.", card_number="#123", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Chrome", attributes="-",
                   team="Kansas City Royals"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    # Prefers the period-suffixed form as the nicer display text, even
    # though it wasn't the first occurrence in the group.
    assert rows[0].player == "Bobby Witt Jr."
    assert ("Daguerreotype", "") in rows[0].parallels
    assert ("Chrome", "") in rows[0].parallels


def test_different_real_names_at_the_same_number_stay_separate():
    # The other side of the same fix: "Goose Gossage" and "Rich
    # Gossage" (his actual first name) sharing 2025 Topps Allen &
    # Ginter #337 is NOT a punctuation artifact - they're genuinely
    # different name text with no safe way to know they're the same
    # person without a nickname dictionary, so they correctly stay two
    # separate rows rather than being guessed into one.
    records = [
        CardRecord(name="Goose Gossage", card_number="#337", set="2025 Topps Allen & Ginter",
                   variant="Base", variant_name="-", attributes="-", team="New York Yankees"),
        CardRecord(name="Rich Gossage", card_number="#337", set="2025 Topps Allen & Ginter",
                   variant="Parallel", variant_name="Chrome", attributes="-",
                   team="New York Yankees"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 2


def test_season_year_formats_use_first_year():
    # "2021-22 Panini Prizm" -> year "2021", not blank
    assert parse_set("2021-22 Panini Prizm") == ("2021", "Panini", "Prizm")
    assert parse_set("2020-21 Topps UEFA") == ("2020", "Topps", "UEFA")
    # YYYY-YYYY four-digit suffix also handled
    assert parse_set("2019-2020 Panini Mosaic") == ("2019", "Panini", "Mosaic")
    # Standard 4-digit year still works
    assert parse_set("2026 Topps") == ("2026", "Topps", "")


def test_split_concatenated_names():
    # Main case: BSC concatenates multiple players with no separator
    assert split_concatenated_names("Dave JollyJim PendletonKarl Spooner") == \
        "Dave Jolly / Jim Pendleton / Karl Spooner"
    # Single name - unchanged
    assert split_concatenated_names("Mike Trout") == "Mike Trout"
    # Two players
    assert split_concatenated_names("Hank AaronWillie Mays") == "Hank Aaron / Willie Mays"
    # Already has spaces everywhere - unchanged
    assert split_concatenated_names("") == ""


def test_split_concatenated_names_protects_common_surname_prefixes():
    # A common surname prefix (Mc/Mac/De/La/Le/Di/Van/Von) sitting right
    # before a lowercase-then-uppercase boundary is NOT a name split point
    # - confirmed at real scale (Brandon, 2026-08-15: 68 rows hit this in
    # one 2025 Allen & Ginter pull alone - "Mark Mc / Gwire" instead of
    # "Mark McGwire").
    protected = [
        "Mark McGwire", "Andrew McCutchen", "Michael McGreevy", "Grant McCray",
        "Shane McClanahan", "Brian McCann", "MacKenzie Gore", "Jacob DeGrom",
        "Adam LaRoche", "DJ LeMahieu", "Joe DiMaggio",
    ]
    for name in protected:
        assert split_concatenated_names(name) == name, f"Failed for {name!r}"

    # A genuine concatenation immediately after a protected prefix still
    # splits correctly at the REAL boundary, not inside the prefix name.
    assert split_concatenated_names("McGwireJohnSmith") == "McGwire / John / Smith"


def test_normalize_team_separators():
    # Comma-separated teams become slash-separated
    assert normalize_team_separators(
        "Milwaukee Braves, Milwaukee Braves, Brooklyn Dodgers"
    ) == "Milwaukee Braves / Milwaukee Braves / Brooklyn Dodgers"
    # Single team - unchanged
    assert normalize_team_separators("Milwaukee Braves") == "Milwaukee Braves"
    assert normalize_team_separators("") == ""


def test_concatenated_names_applied_in_pipeline():
    records = [
        CardRecord(name="Dave JollyJim PendletonKarl Spooner", card_number="#1",
                   set="1956 Topps", variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records)
    assert rows[0].player == "Dave Jolly / Jim Pendleton / Karl Spooner"


def test_team_commas_converted_to_slashes_in_pipeline():
    records = [
        CardRecord(name="Dave Jolly", card_number="#1", set="1956 Topps",
                   variant="Base", variant_name="-", attributes="-",
                   team="Milwaukee Braves, Milwaukee Braves, Brooklyn Dodgers"),
    ]
    rows = convert_and_build(records)
    assert rows[0].team == "Milwaukee Braves / Milwaukee Braves / Brooklyn Dodgers"


def test_clean_description():
    assert clean_description("VAR: Dancing Dodgers Variation") == "Dancing Dodgers"
    assert clean_description("SP: Short Print") == "Short Print"
    assert clean_description("VAR: Batting Stance Variation") == "Batting Stance"
    assert clean_description("") == ""


def test_attributes_extra():
    assert attributes_extra("SP, VAR", "-") == "SP"
    assert attributes_extra("SP", "SP") == ""       # same as base -> nothing extra
    assert attributes_extra("VAR", "-") == ""        # VAR alone is excluded
    assert attributes_extra("-", "-") == ""
    assert attributes_extra("SN50, SP", "-") == "SP" # serial excluded


def test_lettered_variants_group_with_base_and_become_parallels():
    # #1, #1b, #1c should all group under card_number "1".
    # #1b and #1c become parallels using their description field.
    records = [
        CardRecord(name="Shohei Ohtani", card_number="#1", set="2025 Topps",
                   variant="Base", variant_name="-", attributes="-"),
        CardRecord(name="Shohei Ohtani", card_number="#1b", set="2025 Topps",
                   variant="Base", variant_name="-", attributes="SP, VAR",
                   description="VAR: Dancing Dodgers Variation"),
        CardRecord(name="Shohei Ohtani", card_number="#1c", set="2025 Topps",
                   variant="Base", variant_name="-", attributes="SP, VAR",
                   description="VAR: Batting Stance Variation"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "1"
    assert row.player == "Shohei Ohtani"
    # Both lettered variants become parallels with cleaned description + extra attr
    assert ("SP Dancing Dodgers", "") in row.parallels
    assert ("SP Batting Stance", "") in row.parallels


def test_letter_stripped_from_card_number_in_output():
    records = [
        CardRecord(name="Thairo Estrada", card_number="#2b", set="2025 Topps",
                   variant="Base", variant_name="-", attributes="VAR",
                   description="VAR: Fielding Variation"),
    ]
    rows = convert_and_build(records)
    assert rows[0].card_number == "2"
    assert rows[0].parallels == [("Fielding", "")]


def test_non_lettered_card_numbers_not_affected():
    # BA-23, T91-1, 517 should NOT be treated as lettered variants.
    for num in ["#BA-23", "#T91-1", "#517"]:
        records = [
            CardRecord(name="Mike Trout", card_number=num, set="2026 Topps",
                       variant="Base", variant_name="-", attributes="-"),
        ]
        rows = convert_and_build(records)
        assert rows[0].card_number == num.lstrip("#"), f"Failed for {num}"


def test_insert_sharing_base_cards_own_number_still_splits_out():
    # 2026 Donruss Jacob Wilson: base card #13 (with its own normal Optic
    # parallels), and #13 is SEPARATELY the number his unrelated "Diamond
    # Marvels" insert happens to use. The first version of the insert-
    # collision fix assumed a Base row anywhere in the bucket meant
    # everything else was that card's own parallel - which merged Diamond
    # Marvels straight into the base row's parallels with no Insert name
    # at all, instead of splitting it into its own row (Brandon,
    # 2026-08-06, confirmed against the raw export).
    records = [
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Base", variant_name="-", attributes="-"),
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Parallel", variant_name="Artist Proofs", attributes="SN25"),
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Parallel", variant_name="Optic", attributes="-"),
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Parallel", variant_name="Optic Gold", attributes="SN10"),
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Insert", variant_name="Diamond Marvels", attributes="-"),
        CardRecord(name="Jacob Wilson", card_number="#13", set="2026 Donruss",
                   variant="Insert", variant_name="Diamond Marvels Blue Ice", attributes="SN35"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 2

    base_row = next(r for r in rows if not r.insert)
    assert base_row.card_number == "13"
    assert ("Artist Proofs", "25") in base_row.parallels
    assert ("Optic Gold", "10") in base_row.parallels

    insert_row = next(r for r in rows if r.insert)
    assert insert_row.card_number == "13"
    assert insert_row.insert == "Diamond Marvels"
    assert [p[0] for p in insert_row.parallels] == ["Blue Ice"]


def test_leading_apostrophe_stripped_from_card_number():
    # BSC sometimes prefixes card_number with a literal apostrophe ahead
    # of the "#" (its own anti-Excel-autoformat trick) - e.g. "'#DK10".
    # clean_card_number only stripped "#", so the apostrophe survived
    # straight through to the final export (2020 Panini Diamond Kings,
    # confirmed against the raw export, Brandon 2026-08-08 - #DK10 and
    # #206-FT both came out as "'#DK10"/"'#206-FT" instead of clean
    # "DK10"/"206-FT").
    for raw_num, expected in [("'#DK10", "DK10"), ("'#206-FT", "206-FT"), ("#101", "101")]:
        records = [
            CardRecord(name="Frank Thomas", card_number=raw_num, set="2020 Panini",
                       variant="Base", variant_name="-", attributes="-"),
        ]
        rows = convert_and_build(records)
        assert rows[0].card_number == expected, f"Failed for {raw_num!r}"


def test_insert_with_no_bare_row_still_clusters_by_shrinking_anchor():
    # 2020 Panini Diamond Kings' "DK 206 Signatures" insert never prints
    # a bare, un-suffixed row at all - every row already has a color/
    # tier suffix ("...Holo Blue", "...Holo Gold", "...Masterpiece", -
    # confirmed against the raw export, Brandon 2026-08-08). Comparing
    # every row against a FIXED first-row anchor ("...Holo Blue") meant
    # "...Holo Gold" didn't literally start with those exact words and
    # was treated as an unrelated new insert, and so on for every
    # remaining row - the whole insert fragmented into one cluster per
    # parallel instead of staying one card. Fixed by shrinking the
    # anchor to the actual shared prefix as rows disagree, instead of
    # requiring an exact-continuation match against the first row seen.
    records = [
        CardRecord(name="Frank Thomas", card_number="#206-FT", set="2020 Panini",
                   variant="Insert", variant_name="DK 206 Signatures Holo Blue",
                   attributes="AU, SN25"),
        CardRecord(name="Frank Thomas", card_number="#206-FT", set="2020 Panini",
                   variant="Insert", variant_name="DK 206 Signatures Holo Gold",
                   attributes="AU, SN50"),
        CardRecord(name="Frank Thomas", card_number="#206-FT", set="2020 Panini",
                   variant="Insert", variant_name="DK 206 Signatures Masterpiece",
                   attributes="AU, SN1"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].insert == "DK 206 Signatures"
    assert [p[0] for p in rows[0].parallels] == ["Holo Blue", "Holo Gold", "Masterpiece"]


def test_single_word_bare_insert_anchor_still_clusters():
    # Guards the OTHER side of the same fix: an insert whose real name
    # genuinely is just one word ("Anime") must not fragment just
    # because a one-word anchor, on its own, isn't normally enough to
    # continue a cluster (that floor exists to stop two DIFFERENT
    # inserts from merging over one coincidentally shared word). A row
    # that fully extends the anchor as-is is always accepted regardless
    # of word count - only a SHRINKING match is held to the two-word
    # minimum.
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
    ]
    rows = convert_and_build(records)
    assert len(rows) == 1
    assert rows[0].insert == "Anime"


if __name__ == "__main__":
    test_parse_set_brand_is_first_word_rest_is_set()
    test_parse_set_brand_exceptions_loaded_from_csv()
    test_brand_set_exception_preserves_trailing_words()
    test_parse_serial()
    test_trailing_slash_serial_fallback()
    test_normalize_plural_terms_singularizes_without_dropping()
    test_clean_card_number_strips_hash()
    test_extract_card_number_prefix()
    test_split_primary_player_extracts_name_and_leftover()
    test_split_primary_player_not_found_leaves_unchanged()
    test_split_primary_player_handles_trailing_space_on_primary_player()
    test_split_primary_player_handles_leading_and_doubled_internal_space()
    test_longest_common_word_prefix()
    test_strip_common_prefix()
    test_anime_insert_family_full_integration()
    test_base_row_with_only_a_serial_gets_blank_parallel_with_serial()
    test_plain_base_row_no_serial_no_leftover_produces_no_parallel_at_all()
    test_autograph_insert_no_redundant_subtype()
    test_autograph_gets_subtype_when_not_redundant()
    test_card_number_prefix_no_longer_prepended_to_insert()
    test_per_card_fetched_team_overrides_manual_context_team()
    test_primary_player_real_example_integration()
    test_section_records_without_renumbering()
    test_sort_rows_by_brand()
    test_different_card_numbers_do_not_merge()
    test_base_serial_populated_when_base_row_has_serial()
    test_base_serial_blank_when_base_row_has_no_serial()
    test_base_serial_blank_for_insert_only_card()
    test_single_occurrence_insert_card_serial_goes_to_base_serial_not_blank_parallel()
    test_bare_occurrence_with_real_parallel_siblings_keeps_blank_parallel_behavior()
    test_records_with_no_usable_identity_are_dropped_not_ghost_rows()
    test_nno_row_remaps_onto_players_real_base_card_when_one_exists()
    test_nno_placeholder_parallel_rows_treated_as_their_own_card_not_base()
    test_regular_numbered_parallel_with_no_base_row_still_stays_a_parallel()
    test_trailing_period_on_generational_suffix_does_not_split_a_card()
    test_different_real_names_at_the_same_number_stay_separate()
    test_season_year_formats_use_first_year()
    test_split_concatenated_names()
    test_split_concatenated_names_protects_common_surname_prefixes()
    test_normalize_team_separators()
    test_concatenated_names_applied_in_pipeline()
    test_team_commas_converted_to_slashes_in_pipeline()
    test_clean_description()
    test_attributes_extra()
    test_lettered_variants_group_with_base_and_become_parallels()
    test_letter_stripped_from_card_number_in_output()
    test_non_lettered_card_numbers_not_affected()
    test_insert_sharing_base_cards_own_number_still_splits_out()
    test_leading_apostrophe_stripped_from_card_number()
    test_insert_with_no_bare_row_still_clusters_by_shrinking_anchor()
    test_single_word_bare_insert_anchor_still_clusters()
    print("All tests passed.")
