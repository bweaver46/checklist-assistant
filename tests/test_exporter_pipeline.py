"""
Tests for the exporter pipeline logic (Phases 5-7). These don't touch
Playwright at all - they feed fake CardRecords straight in, shaped exactly
like real rows confirmed against the live BuySportsCards table on
2026-06-28 (see settings/selectors.py for the confirmed column layout).
"""

from scraper.card_record import CardRecord
from exporter.convert import convert_all, parse_attributes
from exporter.merge import merge_parallels
from exporter.cleanup import apply_cleanup


def test_parse_attributes():
    assert parse_attributes("SN150") == ("150", False)
    assert parse_attributes("AU, SN150") == ("150", True)
    assert parse_attributes("AU") == ("", True)
    assert parse_attributes("-") == ("", False)
    assert parse_attributes("") == ("", False)


def test_base_row_gets_no_parallel():
    record = CardRecord(
        name="Mike Trout", card_number="#100", set="2026 Bowman",
        variant="Base", variant_name="-", attributes="-",
    )
    row = convert_all([record])[0]
    assert row.parallels == []


def test_insert_parallels_merge_under_same_card_number():
    # Shaped like the real "Anime" rookie insert rows pulled from the
    # live site: same card_number, different variant_name + attributes.
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

    checklist_rows = convert_all(records, context={})
    checklist_rows = merge_parallels(checklist_rows)
    checklist_rows = apply_cleanup(checklist_rows)

    assert len(checklist_rows) == 1
    row = checklist_rows[0]
    assert row.player == "Mike Trout"
    assert row.parallels == [
        ("Anime", ""),
        ("Anime Black Refractors", "10"),
        ("Anime Red Refractors", "5"),
        ("Anime SuperFractors", "1"),
    ]


def test_autograph_flag_appended_to_parallel_name():
    record = CardRecord(
        name="Mike Trout", card_number="#PRV-MT", set="2026 Bowman",
        variant="Insert", variant_name="Rookie and Veteran Autographs Purple",
        attributes="AU, SN250",
    )
    row = convert_all([record])[0]
    assert row.parallels == [("Rookie and Veteran Autographs Purple (AU)", "250")]


def test_different_card_numbers_do_not_merge():
    records = [
        CardRecord(name="Mike Trout", card_number="#100", set="2026 Bowman",
                   variant="Base", variant_name="-", attributes="-"),
        CardRecord(name="Mike Trout", card_number="#BA-23", set="2026 Bowman",
                   variant="Insert", variant_name="Anime", attributes="-"),
    ]
    checklist_rows = merge_parallels(convert_all(records, context={}))
    assert len(checklist_rows) == 2


if __name__ == "__main__":
    test_parse_attributes()
    test_base_row_gets_no_parallel()
    test_insert_parallels_merge_under_same_card_number()
    test_autograph_flag_appended_to_parallel_name()
    test_different_card_numbers_do_not_merge()
    print("All tests passed.")
