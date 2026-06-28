"""
Tests for the exporter pipeline logic (Phases 5-7), using fake CardRecords
shaped exactly like real rows confirmed against the live BuySportsCards
table on 2026-06-28, and the field-mapping rules Brandon gave on the same
date (insert/sub_type/serial are per-occurrence; year/brand parsed from
set; AU -> Autograph unless redundant; plain Base rows dropped).
"""

from scraper.card_record import CardRecord
from exporter.convert import convert_all, parse_set, parse_serial, build_sub_type
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
        ("Anime Black Refractors", "", "10"),
        ("Anime Red Refractors", "", "5"),
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
    print("All tests passed.")
