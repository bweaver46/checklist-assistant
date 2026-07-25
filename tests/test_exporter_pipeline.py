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
    assert row.parallels == [("", "250")]


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
    test_season_year_formats_use_first_year()
    test_split_concatenated_names()
    test_normalize_team_separators()
    test_concatenated_names_applied_in_pipeline()
    test_team_commas_converted_to_slashes_in_pipeline()
    test_clean_description()
    test_attributes_extra()
    test_lettered_variants_group_with_base_and_become_parallels()
    test_letter_stripped_from_card_number_in_output()
    test_non_lettered_card_numbers_not_affected()
    print("All tests passed.")
