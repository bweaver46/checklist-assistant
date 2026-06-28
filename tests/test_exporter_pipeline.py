"""
Tests for the exporter pipeline logic (Phases 5-7), using fake CardRecords
shaped exactly like real rows confirmed against the live BuySportsCards
table, and the field-mapping rules Brandon gave on 2026-06-28-2026-06-29:
    - insert/sub_type/serial are per-occurrence
    - year/brand parsed from set; `set` itself holds brand only (no year)
    - AU -> Autograph unless redundant; PR treated the same as SN
    - plain Base rows dropped unless something's worth keeping
    - insert-name normalization: hyphens->spaces, redundant trailing
      Refractor dropped, Prizm/Refractor plurals normalized - all BEFORE
      a card-number prefix (e.g. "T91-") gets prepended, so the prefix's
      own hyphen survives
    - "#" stripped from card_number; non-numeric prefix moved to insert
    - Primary Player context value extracts a player's name out of a
      messy Name field, moving the rest into sub_type
"""

from scraper.card_record import CardRecord
from exporter.convert import (
    convert_all, parse_set, parse_serial, build_sub_type,
    split_trailing_slash_serial, normalize_insert_name,
    clean_card_number, extract_card_number_prefix, split_primary_player,
)
from exporter.merge import merge_parallels
from exporter.cleanup import apply_cleanup


def test_parse_set():
    assert parse_set("2026 Bowman") == ("2026", "Bowman")
    assert parse_set("Bowman") == ("", "Bowman")
    assert parse_set("") == ("", "")


def test_parse_serial():
    assert parse_serial("SN150") == "150"
    assert parse_serial("AU, SN150") == "150"
    assert parse_serial("AU") == ""
    assert parse_serial("-") == ""
    assert parse_serial("PR99") == "99"
    assert parse_serial("AU, PR99") == "99"


def test_build_sub_type_autograph():
    assert build_sub_type("AU, SN150", "2026 Bowman", "Some Insert") == "Autograph"
    assert build_sub_type("AU, SN250", "2026 Bowman",
                           "Rookie and Veteran Autographs Purple") == ""
    assert build_sub_type("AU", "2026 Bowman Autographs", "") == ""


def test_print_run_never_appears_in_sub_type():
    assert build_sub_type("PR99", "2026 Bowman", "Some Insert") == ""
    assert build_sub_type("AU, PR99", "2026 Bowman", "Some Insert") == "Autograph"


def test_set_column_holds_brand_only_no_year():
    record = CardRecord(
        name="Mike Trout", card_number="100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="SN50",
    )
    row = convert_all([record])[0]
    assert row.set == "Bowman"
    assert row.year == "2026"
    assert row.brand == "Bowman"


def test_plain_base_row_produces_no_occurrence():
    record = CardRecord(
        name="Mike Trout", card_number="100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.occurrences == []


def test_base_with_attributes_is_kept_with_blank_insert():
    record = CardRecord(
        name="Mike Trout", card_number="100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="SN50",
    )
    row = convert_all([record])[0]
    assert row.occurrences == [("", "", "50")]


def test_insert_occurrences_merge_under_same_card_number():
    # card_number "#BA-23" has a trailing digit run ("23"), so "BA-" is
    # a real prefix that gets prepended to insert text - but only AFTER
    # the Refractor-stripping normalization already ran, so it doesn't
    # collide with that rule.
    records = [
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Black Refractors", attributes="SN10"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime Red Refractors", attributes="SN5"),
    ]

    checklist_rows = apply_cleanup(merge_parallels(convert_all(records, {})))

    assert len(checklist_rows) == 1
    row = checklist_rows[0]
    assert row.player == "Mike Trout"
    assert row.year == "2026"
    assert row.brand == "Bowman"
    assert row.set == "Bowman"
    assert row.card_number == "BA-23"
    assert row.occurrences == [
        ("BA- Anime", "", ""),
        ("BA- Anime Black", "", "10"),
        ("BA- Anime Red", "", "5"),
    ]


def test_autograph_insert_gets_blank_subtype_no_duplicate():
    # "PRV-MT" has no trailing digit at all, so no prefix gets extracted.
    record = CardRecord(
        name="Mike Trout", card_number="#PRV-MT", set="2026 Bowman",
        variant="Insert", variant_name="Rookie and Veteran Autographs Purple",
        attributes="AU, SN250",
    )
    row = convert_all([record])[0]
    assert row.card_number == "PRV-MT"
    assert row.occurrences == [("Rookie and Veteran Autographs Purple", "", "250")]


def test_different_card_numbers_do_not_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Bowman",
                   variant="Base", variant_name="-", attributes="SN50"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
    ]
    checklist_rows = merge_parallels(convert_all(records, {}))
    assert len(checklist_rows) == 2


def test_plain_base_with_section_still_keeps_section():
    record = CardRecord(
        name="Mike Trout", card_number="#101", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record], {"section": "Prospects"})[0]
    assert row.set == "Bowman"
    assert row.card_number == "101"
    assert row.occurrences == [("", "Prospects", "")]


def test_section_combines_with_autograph_without_duplication():
    record = CardRecord(
        name="Mike Trout", card_number="#PRV-MT", set="2026 Bowman",
        variant="Insert", variant_name="Rookie and Veteran Autographs Purple",
        attributes="AU, SN250",
    )
    context = {"section": "Prospects"}
    row = convert_all([record], context)[0]
    assert row.occurrences == [
        ("Rookie and Veteran Autographs Purple", "Prospects", "250")
    ]


def test_trailing_slash_serial_fallback():
    assert split_trailing_slash_serial("Gold /50") == ("Gold", "50")
    assert split_trailing_slash_serial("Anime") == ("Anime", "")


def test_normalize_insert_name_hyphens_and_spacing():
    assert normalize_insert_name("Black-Wave") == "Black Wave"
    assert normalize_insert_name("Black  Wave") == "Black Wave"
    assert normalize_insert_name("  Black Wave  ") == "Black Wave"


def test_normalize_insert_name_drops_trailing_refractor():
    assert normalize_insert_name("Blue Mojo Refractor") == "Blue Mojo"
    assert normalize_insert_name("Blue Mojo Refractors") == "Blue Mojo"
    assert normalize_insert_name("Blue Mojo") == "Blue Mojo"


def test_normalize_insert_name_prizm_and_refractor_plurals():
    assert normalize_insert_name("Silver Prizms") == "Silver Prizm"
    assert normalize_insert_name("Silver Prizm") == "Silver Prizm"
    assert normalize_insert_name("Refractors Wave") == "Refractor Wave"


def test_standardize_names_merges_hyphen_variants_after_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Black-Wave", attributes="SN10"),
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Black Wave", attributes="SN10"),
    ]
    checklist_rows = apply_cleanup(merge_parallels(convert_all(records, {})))
    assert len(checklist_rows) == 1
    assert checklist_rows[0].occurrences == [("Black Wave", "", "10")]


def test_standardize_names_merges_refractor_variants_after_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Panini Prizm",
                   variant="Insert", variant_name="Blue Mojo", attributes="SN10"),
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Panini Prizm",
                   variant="Insert", variant_name="Blue Mojo Refractor", attributes="SN10"),
    ]
    checklist_rows = apply_cleanup(merge_parallels(convert_all(records, {})))
    assert len(checklist_rows) == 1
    assert checklist_rows[0].occurrences == [("Blue Mojo", "", "10")]


# --- Card number prefix (Rule 2) ---

def test_clean_card_number_strips_hash():
    assert clean_card_number("#T91-1") == "T91-1"
    assert clean_card_number("517") == "517"
    assert clean_card_number("") == ""


def test_extract_card_number_prefix():
    assert extract_card_number_prefix("T91-1") == "T91-"
    assert extract_card_number_prefix("TBC15") == "TBC"
    assert extract_card_number_prefix("517") == ""
    assert extract_card_number_prefix("12P5") == "12P"
    assert extract_card_number_prefix("") == ""


def test_card_number_prefix_prepended_to_insert_and_hyphen_survives():
    # "T91-" must keep its hyphen even though normalize_insert_name
    # strips hyphens elsewhere - the prefix is applied AFTER that step.
    record = CardRecord(
        name="Mike Trout", card_number="#T91-1", set="1991 Topps",
        variant="Insert", variant_name="35th Anniversary", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.card_number == "T91-1"
    assert row.occurrences == [("T91- 35th Anniversary", "", "")]


def test_card_number_prefix_alone_keeps_otherwise_plain_base_row():
    # A Base row with nothing else notable would normally be dropped -
    # but if its card_number has a prefix, that prefix must not be lost.
    record = CardRecord(
        name="Mike Trout", card_number="#T91-1", set="1991 Topps",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.occurrences == [("T91-", "", "")]


def test_purely_numeric_card_number_gets_no_prefix():
    record = CardRecord(
        name="Mike Trout", card_number="#517", set="2026 Topps",
        variant="Insert", variant_name="Some Insert", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.card_number == "517"
    assert row.occurrences == [("Some Insert", "", "")]


# --- Primary Player splitting (Rule 3) ---

def test_split_primary_player_extracts_name_and_leftover():
    name, leftover = split_primary_player(
        "Stars Align (Mike TroutZach Neto) CPC", "Mike Trout"
    )
    assert name == "Mike Trout"
    assert leftover == "Stars Align (Zach Neto) CPC"


def test_split_primary_player_blank_leaves_name_unchanged():
    name, leftover = split_primary_player("Mike Trout", "")
    assert name == "Mike Trout"
    assert leftover == ""


def test_split_primary_player_not_found_leaves_name_unchanged():
    name, leftover = split_primary_player("Shohei Ohtani", "Mike Trout")
    assert name == "Shohei Ohtani"
    assert leftover == ""


def test_primary_player_integration_real_example():
    record = CardRecord(
        name="Stars Align (Mike TroutZach Neto) CPC", card_number="#517",
        set="2026 Topps", variant="Base", variant_name="-", attributes="-",
    )
    context = {"primary_player": "Mike Trout"}
    row = convert_all([record], context)[0]
    assert row.player == "Mike Trout"
    assert row.occurrences == [("", "Stars Align (Zach Neto) CPC", "")]


def test_primary_player_leftover_combines_with_autograph():
    record = CardRecord(
        name="Stars Align (Mike Trout Zach Neto) CPC AU", card_number="#517",
        set="2026 Topps", variant="Insert", variant_name="Some Insert",
        attributes="AU, SN50",
    )
    context = {"primary_player": "Mike Trout"}
    row = convert_all([record], context)[0]
    assert row.player == "Mike Trout"
    insert, sub_type, serial = row.occurrences[0]
    assert "Stars Align" in sub_type
    assert "Zach Neto" in sub_type
    assert serial == "50"


if __name__ == "__main__":
    test_parse_set()
    test_parse_serial()
    test_build_sub_type_autograph()
    test_print_run_never_appears_in_sub_type()
    test_set_column_holds_brand_only_no_year()
    test_plain_base_row_produces_no_occurrence()
    test_base_with_attributes_is_kept_with_blank_insert()
    test_insert_occurrences_merge_under_same_card_number()
    test_autograph_insert_gets_blank_subtype_no_duplicate()
    test_different_card_numbers_do_not_merge()
    test_plain_base_with_section_still_keeps_section()
    test_section_combines_with_autograph_without_duplication()
    test_trailing_slash_serial_fallback()
    test_normalize_insert_name_hyphens_and_spacing()
    test_normalize_insert_name_drops_trailing_refractor()
    test_normalize_insert_name_prizm_and_refractor_plurals()
    test_standardize_names_merges_hyphen_variants_after_merge()
    test_standardize_names_merges_refractor_variants_after_merge()
    test_clean_card_number_strips_hash()
    test_extract_card_number_prefix()
    test_card_number_prefix_prepended_to_insert_and_hyphen_survives()
    test_card_number_prefix_alone_keeps_otherwise_plain_base_row()
    test_purely_numeric_card_number_gets_no_prefix()
    test_split_primary_player_extracts_name_and_leftover()
    test_split_primary_player_blank_leaves_name_unchanged()
    test_split_primary_player_not_found_leaves_name_unchanged()
    test_primary_player_integration_real_example()
    test_primary_player_leftover_combines_with_autograph()
    print("All tests passed.")
