"""
Tests for settings/last_search.py - remembering the last-used "Build a
Search" field values (Brandon, 2026-08-16: "when adding a search it
should maintain all of the fields from the last time it was filled out
so that if only one field changes I don't have to fill it out again").
"""

import settings.last_search as last_search


def test_load_last_search_returns_empty_dict_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(last_search, "LAST_SEARCH_PATH", tmp_path / "last_search.json")
    assert last_search.load_last_search() == {}


def test_save_then_load_round_trips_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(last_search, "LAST_SEARCH_PATH", tmp_path / "last_search.json")
    fields = {"keyword": "Griffey", "sport": "Baseball", "year": "1989", "set": ""}
    last_search.save_last_search(fields)
    assert last_search.load_last_search() == fields


def test_save_overwrites_previous_values(tmp_path, monkeypatch):
    monkeypatch.setattr(last_search, "LAST_SEARCH_PATH", tmp_path / "last_search.json")
    last_search.save_last_search({"keyword": "Griffey", "sport": "Baseball"})
    last_search.save_last_search({"keyword": "Ripken", "sport": "Baseball"})
    assert last_search.load_last_search() == {"keyword": "Ripken", "sport": "Baseball"}


def test_load_last_search_ignores_corrupt_file(tmp_path, monkeypatch):
    bad_path = tmp_path / "last_search.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(last_search, "LAST_SEARCH_PATH", bad_path)
    assert last_search.load_last_search() == {}
