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
)
from exporter.merge import build_checklist_rows, longest_common_word_prefix, strip_common_prefix
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
    assert extract_card_number_prefix("T91-1") == "T91-"
    assert extract_card_number_prefix("TBC15") == "TBC"
    assert extract_card_number_prefix("517") == ""
    assert extract_card_number_prefix("12P5") == "12P"


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
    assert row.insert == "BA- Anime"  # card-number prefix prepended
    assert row.sub_type == ""
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
    assert row.sub_type == ""  # "Autograph" already implied by insert text
    assert row.parallels == [("", "250")]


def test_autograph_gets_subtype_when_not_redundant():
    records = [
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Some Insert", attributes="AU, SN50"),
    ]
    rows = convert_and_build(records)
    assert rows[0].sub_type == "Autograph"


def test_card_number_prefix_with_hyphen_survives_normalization():
    records = [
        CardRecord(name="Mike Trout", card_number="#T91-1", set="1991 Topps Baseball",
                   variant="Insert", variant_name="35th Anniversary (Series One)",
                   attributes="-"),
    ]
    rows = convert_and_build(records, {"team": "Los Angeles Angels"})
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "T91-1"
    assert row.insert == "T91- 35th Anniversary (Series One)"
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
    assert row.sub_type == "Stars Align (Zach Neto) CPC"


def test_section_records_without_renumbering():
    records = [
        CardRecord(name="Mike Trout", card_number="#351", set="2026 Topps",
                   variant="Base", variant_name="-", attributes="-"),
    ]
    rows = convert_and_build(records, {"section": "Series 2"})
    assert len(rows) == 1
    row = rows[0]
    assert row.card_number == "351"
    assert row.sub_type == "Series 2"


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
    test_longest_common_word_prefix()
    test_strip_common_prefix()
    test_anime_insert_family_full_integration()
    test_base_row_with_only_a_serial_gets_blank_parallel_with_serial()
    test_plain_base_row_no_serial_no_leftover_produces_no_parallel_at_all()
    test_autograph_insert_no_redundant_subtype()
    test_autograph_gets_subtype_when_not_redundant()
    test_card_number_prefix_with_hyphen_survives_normalization()
    test_per_card_fetched_team_overrides_manual_context_team()
    test_primary_player_real_example_integration()
    test_section_records_without_renumbering()
    test_sort_rows_by_brand()
    test_different_card_numbers_do_not_merge()
    print("All tests passed.")
