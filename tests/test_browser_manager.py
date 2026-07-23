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


class FakeYearRow:
    def __init__(self, player_name, year, card_number="1"):
        self.player_name = player_name
        self.year = year
        self.card_number = card_number


def _read_year_row(row):
    return CardRecord(name=row.player_name, card_number=row.card_number, set=f"{row.year} Some Product")


def test_year_sampling_resolves_after_matching_samples():
    # 3 rows from the same year, all the same team -> resolves after
    # exactly 3 fetches; a 4th row of the same year reuses the cached
    # team with no further fetch.
    bm = BrowserManager()
    fake_rows = [FakeYearRow("Shohei Ohtani", "2023") for _ in range(4)]
    bm._page = FakePage(fake_rows)
    bm.read_row = _read_year_row

    call_log = []
    bm.fetch_card_details_for_row = lambda row: (call_log.append(1) or "Los Angeles Angels", "")

    records = bm.read_all_rows(fetch_team=True, sample_team_by_year=True)

    assert len(call_log) == 3, f"expected exactly 3 fetches, got {len(call_log)}"
    assert all(r.team == "Los Angeles Angels" for r in records)


def test_year_sampling_falls_back_to_full_fetch_on_disagreement():
    # 3 samples where the 3rd disagrees (a mid-season trade) -> MIXED,
    # so a 4th and 5th row of that same year both still get fetched
    # individually instead of reusing anything.
    bm = BrowserManager()
    fake_rows = [FakeYearRow("Shohei Ohtani", "2024") for _ in range(5)]
    bm._page = FakePage(fake_rows)
    bm.read_row = _read_year_row

    teams = ["Los Angeles Angels", "Los Angeles Angels", "Los Angeles Dodgers",
             "Los Angeles Dodgers", "Los Angeles Dodgers"]
    call_log = []

    def fake_fetch(row):
        call_log.append(1)
        return teams[len(call_log) - 1]

    bm.fetch_card_details_for_row = lambda row: (fake_fetch(row), "")

    records = bm.read_all_rows(fetch_team=True, sample_team_by_year=True)

    # All 5 rows fetched - 3 samples plus 2 more after MIXED was detected.
    assert len(call_log) == 5, f"expected all 5 rows fetched once MIXED, got {len(call_log)}"
    assert [r.team for r in records] == teams


def test_year_sampling_keeps_separate_years_independent():
    # 3 matching samples for 2023 (resolves), then a fresh 2024 row
    # must NOT reuse 2023's resolved team - it's a different bucket and
    # needs its own samples.
    bm = BrowserManager()
    fake_rows = (
        [FakeYearRow("Shohei Ohtani", "2023") for _ in range(3)]
        + [FakeYearRow("Shohei Ohtani", "2024")]
    )
    bm._page = FakePage(fake_rows)
    bm.read_row = _read_year_row

    call_log = []

    def fake_fetch(row):
        call_log.append(row.year)
        return "Los Angeles Angels" if row.year == "2023" else "Los Angeles Dodgers"

    bm.fetch_card_details_for_row = lambda row: (fake_fetch(row), "")

    records = bm.read_all_rows(fetch_team=True, sample_team_by_year=True)

    # 3 fetches for 2023 (to resolve it) + 1 fetch for the first-ever
    # 2024 row (its own bucket, still sampling) = 4 total.
    assert len(call_log) == 4
    assert records[0].team == records[1].team == records[2].team == "Los Angeles Angels"
    assert records[3].team == "Los Angeles Dodgers"


def test_year_sampling_lettered_variant_rows_are_untouched():
    # Lettered variants (e.g. "1b") always fetch regardless of mode -
    # sample_team_by_year should not interfere with that existing rule.
    bm = BrowserManager()
    row = FakeYearRow("Shohei Ohtani", "2023", card_number="1b")
    bm._page = FakePage([row])
    bm.read_row = _read_year_row

    call_log = []
    bm.fetch_card_details_for_row = lambda r: (call_log.append(1) or "Los Angeles Angels", "desc")

    records = bm.read_all_rows(fetch_team=False, sample_team_by_year=True)

    assert len(call_log) == 1
    assert records[0].team == "Los Angeles Angels"
    assert records[0].description == "desc"


if __name__ == "__main__":
    test_team_cache_only_fetches_once_per_distinct_player()
    test_team_cache_does_not_fetch_at_all_when_fetch_team_is_false()
    test_team_cache_persists_across_extraction_runs()
    test_year_sampling_resolves_after_matching_samples()
    test_year_sampling_falls_back_to_full_fetch_on_disagreement()
    test_year_sampling_keeps_separate_years_independent()
    test_year_sampling_lettered_variant_rows_are_untouched()
    print("All tests passed.")
