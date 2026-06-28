"""
Tests for the exporter pipeline logic (Phases 5-7), using fake CardRecords
shaped exactly like real rows confirmed against the live BuySportsCards
table on 2026-06-28, and the field-mapping rules Brandon gave on the same
date (insert/sub_type/serial are per-occurrence; year/brand parsed from
set; AU -> Autograph unless redundant; plain Base rows dropped).
"""

from scraper.card_record import CardRecord
from exporter.convert import (
    convert_all, parse_set, parse_serial, build_sub_type,
    split_trailing_slash_serial,
)
from exporter.merge import merge_parallels
from exporter.cleanup import apply_cleanup, normalize_insert_name


def test_parse_set():
    assert parse_set("2026 Bowman") == ("2026", "Bowman")
    assert parse_set("Bowman") == ("", "Bowman")
    assert parse_set("") == ("", "")


def test_parse_serial():
    assert parse_serial("SN150") == "150"
    assert parse_serial("AU, SN150") == "150"
    assert parse_serial("AU") == ""
    assert parse_serial("-") == ""
    # PR (Print Run) is the same concept as SN under a different label.
    assert parse_serial("PR99") == "99"
    assert parse_serial("AU, PR99") == "99"


def test_build_sub_type_autograph():
    # No "Autograph" anywhere else -> AU becomes "Autograph"
    assert build_sub_type("AU, SN150", "2026 Bowman", "Some Insert") == "Autograph"
    # "Autograph" already in the insert name -> dropped, not duplicated
    assert build_sub_type("AU, SN250", "2026 Bowman",
                           "Rookie and Veteran Autographs Purple") == ""
    # "Autograph" already in the set name -> dropped
    assert build_sub_type("AU", "2026 Bowman Autographs", "") == ""


def test_print_run_never_appears_in_sub_type():
    # PR is just a serial label, not a sub_type category - sub_type
    # should stay blank even when PR is present.
    assert build_sub_type("PR99", "2026 Bowman", "Some Insert") == ""
    assert build_sub_type("AU, PR99", "2026 Bowman", "Some Insert") == "Autograph"


def test_plain_base_row_produces_no_occurrence():
    record = CardRecord(
        name="Mike Trout", card_number="#100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.occurrences == []
    assert row.year == "2026"
    assert row.brand == "Bowman"


def test_base_with_attributes_is_kept_with_blank_insert():
    record = CardRecord(
        name="Mike Trout", card_number="#100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="SN50",
    )
    row = convert_all([record])[0]
    assert row.occurrences == [("", "", "50")]


def test_insert_occurrences_merge_under_same_card_number():
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
    assert row.occurrences == [
        ("Anime", "", ""),
        ("Anime Black", "", "10"),
        ("Anime Red", "", "5"),
    ]


def test_autograph_insert_gets_blank_subtype_no_duplicate():
    record = CardRecord(
        name="Mike Trout", card_number="#PRV-MT", set="2026 Bowman",
        variant="Insert", variant_name="Rookie and Veteran Autographs Purple",
        attributes="AU, SN250",
    )
    row = convert_all([record])[0]
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
    # Without a section, a plain Base row produces no occurrence at all.
    # With a section like "Prospects", that would silently lose the
    # section name - so an occurrence must still be created.
    record = CardRecord(
        name="Mike Trout", card_number="#101", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record], {"section": "Prospects"})[0]
    assert row.set == "2026 Bowman"
    assert row.card_number == "#101"
    assert row.occurrences == [("", "Prospects", "")]


def test_normalize_insert_name_drops_trailing_refractor():
    assert normalize_insert_name("Blue Mojo Refractor") == "Blue Mojo"
    assert normalize_insert_name("Blue Mojo Refractors") == "Blue Mojo"
    assert normalize_insert_name("Blue Mojo") == "Blue Mojo"


def test_normalize_insert_name_prizm_and_refractor_plurals():
    assert normalize_insert_name("Silver Prizms") == "Silver Prizm"
    assert normalize_insert_name("Silver Prizm") == "Silver Prizm"
    # Non-trailing "Refractor" (not at the end) still gets singular-normalized
    # rather than dropped.
    assert normalize_insert_name("Refractors Wave") == "Refractor Wave"


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


def test_standardize_names_merges_hyphen_variants_after_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Black-Wave", attributes="SN10"),
        CardRecord(name="Mike Trout", card_number="#XYZ", set="2026 Bowman",
                   variant="Insert", variant_name="Black Wave", attributes="SN10"),
    ]
    checklist_rows = apply_cleanup(merge_parallels(convert_all(records, {})))
    assert len(checklist_rows) == 1
    # After normalization both occurrences are identical and get deduped.
    assert checklist_rows[0].occurrences == [("Black Wave", "", "10")]


if __name__ == "__main__":
    test_parse_set()
    test_parse_serial()
    test_build_sub_type_autograph()
    test_print_run_never_appears_in_sub_type()
    test_plain_base_row_produces_no_occurrence()
    test_base_with_attributes_is_kept_with_blank_insert()
    test_insert_occurrences_merge_under_same_card_number()
    test_autograph_insert_gets_blank_subtype_no_duplicate()
    test_different_card_numbers_do_not_merge()
    test_plain_base_with_section_still_keeps_section()
    test_section_combines_with_autograph_without_duplication()
    test_trailing_slash_serial_fallback()
    test_normalize_insert_name_hyphens_and_spacing()
    test_standardize_names_merges_hyphen_variants_after_merge()
    test_normalize_insert_name_drops_trailing_refractor()
    test_normalize_insert_name_prizm_and_refractor_plurals()
    test_standardize_names_merges_refractor_variants_after_merge()
    print("All tests passed.")
