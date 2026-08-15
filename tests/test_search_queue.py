"""
Tests for scraper/search_queue.py - staged searches, persistence, and
which ones are eligible for a later queue-runner to actually pull.
"""

import json

from scraper.search_queue import (
    StagedSearch, load_queue, save_queue, passed_entries,
    UNTESTED, PASSED, FAILED, QUEUE_PATH,
)


def _cleanup():
    if QUEUE_PATH.exists():
        QUEUE_PATH.unlink()


def test_new_entry_defaults_to_untested():
    entry = StagedSearch(name="Test", fields={"keyword": "206"})
    assert entry.status == UNTESTED
    assert entry.status_detail == ""


def test_url_builds_from_fields():
    entry = StagedSearch(name="Diamond Kings", fields={
        "keyword": "206", "sport": "Baseball", "year": "2020",
        "set": "Panini Diamond Kings",
    })
    assert "q=206" in entry.url()
    assert "sport[]=baseball" in entry.url()


def test_display_line_reflects_status():
    entry = StagedSearch(name="X", status=UNTESTED)
    assert "○" in entry.display_line()
    entry.status = PASSED
    assert "✓" in entry.display_line()
    entry.status = FAILED
    entry.status_detail = "No results found for this search."
    line = entry.display_line()
    assert "✗" in line
    assert "No results found for this search." in line


def test_save_and_load_round_trip():
    try:
        entries = [
            StagedSearch(name="A", fields={"keyword": "foo"}, status=PASSED, status_detail="3 result(s)"),
            StagedSearch(name="B", fields={"keyword": "bar"}, status=FAILED, status_detail="No results found for this search."),
        ]
        save_queue(entries)
        loaded = load_queue()
        assert len(loaded) == 2
        assert loaded[0].name == "A"
        assert loaded[0].status == PASSED
        assert loaded[1].status == FAILED
        assert loaded[1].status_detail == "No results found for this search."
    finally:
        _cleanup()


def test_load_queue_missing_file_returns_empty():
    _cleanup()
    assert load_queue() == []


def test_load_queue_corrupt_file_returns_empty_not_crash():
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text("not valid json{{{", encoding="utf-8")
    try:
        assert load_queue() == []
    finally:
        _cleanup()


def test_passed_entries_excludes_untested_and_failed():
    entries = [
        StagedSearch(name="A", status=PASSED),
        StagedSearch(name="B", status=FAILED),
        StagedSearch(name="C", status=UNTESTED),
        StagedSearch(name="D", status=PASSED),
    ]
    result = passed_entries(entries)
    assert [e.name for e in result] == ["A", "D"]


if __name__ == "__main__":
    test_new_entry_defaults_to_untested()
    test_url_builds_from_fields()
    test_display_line_reflects_status()
    test_save_and_load_round_trip()
    test_load_queue_missing_file_returns_empty()
    test_load_queue_corrupt_file_returns_empty_not_crash()
    test_passed_entries_excludes_untested_and_failed()
    print("All search_queue tests passed.")
