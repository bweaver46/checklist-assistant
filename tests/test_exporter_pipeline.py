"""
Tests for the exporter pipeline logic (Phases 5-7). These don't touch
Playwright at all - they feed fake CardRecords straight in, the way real
extracted rows would arrive, and check the pipeline produces the merged,
cleaned-up checklist rows described in the vision doc's Mike Trout example.
"""

from scraper.card_record import CardRecord
from exporter.convert import convert_all, split_serial
from exporter.merge import merge_parallels
from exporter.cleanup import apply_cleanup


def test_split_serial():
    assert split_serial("Gold /50") == ("Gold", "50")
    assert split_serial("Base") == ("Base", "")
    assert split_serial("") == ("", "")


def test_mike_trout_example_merges_and_cleans_up():
    raw_records = [
        CardRecord(name="Mike Trout", card_number="1", set="2026 Topps", variant="Base"),
        CardRecord(name="Mike Trout", card_number="1", set="2026 Topps", variant="Gold /50"),
        CardRecord(name="Mike Trout", card_number="1", set="2026 Topps", variant="Red /05"),
    ]

    checklist_rows = convert_all(raw_records, context={})
    checklist_rows = merge_parallels(checklist_rows)
    checklist_rows = apply_cleanup(checklist_rows)

    assert len(checklist_rows) == 1
    row = checklist_rows[0]
    assert row.player == "Mike Trout"
    # Base should have been dropped, leaving just Gold and Red.
    assert row.parallels == [("Gold", "50"), ("Red", "5")]


def test_different_players_do_not_merge():
    raw_records = [
        CardRecord(name="Mike Trout", card_number="1", set="2026 Topps", variant="Base"),
        CardRecord(name="Shohei Ohtani", card_number="2", set="2026 Topps", variant="Base"),
    ]

    checklist_rows = convert_all(raw_records, context={})
    checklist_rows = merge_parallels(checklist_rows)

    assert len(checklist_rows) == 2
    players = {row.player for row in checklist_rows}
    assert players == {"Mike Trout", "Shohei Ohtani"}


if __name__ == "__main__":
    test_split_serial()
    test_mike_trout_example_merges_and_cleans_up()
    test_different_players_do_not_merge()
    print("All tests passed.")
