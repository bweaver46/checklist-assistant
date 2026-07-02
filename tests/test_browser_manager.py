"""
Tests for BrowserManager logic that doesn't actually need a live
browser - specifically the per-player team cache added 2026-06-29
(Brandon's observation: most rows in a set are parallels of the SAME
player, so "Add" only needs to be clicked once per distinct player
name, not once per row).

Uses lightweight fakes for Page/Locator/Row rather than real Playwright
objects, with read_row and fetch_card_details_for_row monkeypatched - this lets
us verify the caching behavior in isolation without a browser.
"""

from scraper.browser_manager import BrowserManager
from scraper.card_record import CardRecord


class FakeLocator:
    def __init__(self, items):
        self._items = items

    def count(self):
        return len(self._items)

    def nth(self, i):
        return self._items[i]


class FakeRow:
    def __init__(self, player_name):
        self.player_name = player_name


class FakePage:
    def __init__(self, rows):
        self._rows = rows

    def locator(self, selector):
        return FakeLocator(self._rows)


def test_team_cache_only_fetches_once_per_distinct_player():
    bm = BrowserManager()
    fake_rows = [
        FakeRow("Mike Trout"),
        FakeRow("Mike Trout"),  # a parallel of the same card - should hit cache
        FakeRow("Zach Neto"),
        FakeRow("Mike Trout"),  # yet another parallel - still cached
    ]
    bm._page = FakePage(fake_rows)
    bm.read_row = lambda row: CardRecord(name=row.player_name)

    call_log = []

    def fake_fetch(row):
        call_log.append(row.player_name)
        return {"Mike Trout": "Los Angeles Angels", "Zach Neto": "Boston Red Sox"}[row.player_name]

    bm.fetch_card_details_for_row = lambda row: (fake_fetch(row), "")

    records = bm.read_all_rows(fetch_team=True)

    # Only 2 distinct players -> only 2 actual fetches, not 4.
    assert call_log == ["Mike Trout", "Zach Neto"]
    assert [r.team for r in records] == [
        "Los Angeles Angels",
        "Los Angeles Angels",
        "Boston Red Sox",
        "Los Angeles Angels",
    ]


def test_team_cache_does_not_fetch_at_all_when_fetch_team_is_false():
    bm = BrowserManager()
    fake_rows = [FakeRow("Mike Trout"), FakeRow("Mike Trout")]
    bm._page = FakePage(fake_rows)
    bm.read_row = lambda row: CardRecord(name=row.player_name)

    call_log = []
    bm.fetch_card_details_for_row = lambda row: (call_log.append(row.player_name), "")[1] or ("", "")

    records = bm.read_all_rows(fetch_team=False)

    assert call_log == []
    assert all(r.team == "" for r in records)


def test_team_cache_persists_across_extraction_runs():
    # The cache is now managed by ExtractionWorker (loaded from disk before
    # each run, saved after). extract_all_pages() no longer resets it, so a
    # player seen in run 1 is NOT re-fetched in run 2.
    bm = BrowserManager()
    bm._team_cache = {"Mike Trout": "Los Angeles Angels"}  # pre-loaded from disk
    bm.has_next_page = lambda: False
    bm.read_row = lambda row: CardRecord(name=row.player_name)

    fake_rows = [FakeRow("Mike Trout")]
    bm._page = FakePage(fake_rows)

    call_log = []

    def fake_fetch(row):
        call_log.append(row.player_name)
        return "Fresh Team"

    bm.fetch_card_details_for_row = lambda row: (fake_fetch(row), "")

    records = bm.extract_all_pages(fetch_team=True)

    # Cache hit - no fetch should have happened.
    assert call_log == []
    assert records[0].team == "Los Angeles Angels"


if __name__ == "__main__":
    test_team_cache_only_fetches_once_per_distinct_player()
    test_team_cache_does_not_fetch_at_all_when_fetch_team_is_false()
    test_team_cache_persists_across_extraction_runs()
    print("All tests passed.")
