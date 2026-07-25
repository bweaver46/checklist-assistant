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


def test_year_checkin_fetches_first_row_then_assumes_until_recheck_interval():
    # With the recheck interval patched to 3: row 1 fetches (establishes
    # the assumption), rows 2-3 reuse it with no fetch, row 4 is the
    # recheck (fetches again). All agree, so only rows 1 and 4 fetch.
    import scraper.browser_manager as browser_manager_module
    original_interval = browser_manager_module.TEAM_RECHECK_INTERVAL
    browser_manager_module.TEAM_RECHECK_INTERVAL = 3
    try:
        bm = BrowserManager()
        fake_rows = [FakeYearRow("Shohei Ohtani", "2023") for _ in range(6)]
        bm._page = FakePage(fake_rows)
        bm.read_row = _read_year_row

        call_log = []
        bm.fetch_card_details_for_row = lambda row: (call_log.append(1) or "Los Angeles Angels", "")

        records = bm.read_all_rows(fetch_team=True, sample_team_by_year=True)

        # Row 1 (initial) + row 4 (recheck) = 2 fetches for 6 rows.
        assert len(call_log) == 2, f"expected 2 fetches (row 1 + row 4 recheck), got {len(call_log)}"
        assert all(r.team == "Los Angeles Angels" for r in records)
    finally:
        browser_manager_module.TEAM_RECHECK_INTERVAL = original_interval


def test_year_checkin_switches_to_full_fetch_after_recheck_disagrees():
    # Row 1 establishes Angels. Rows 2-3 assumed. Row 4 (recheck) comes
    # back Dodgers -> disagreement -> MIXED. Rows 5-6 must each be
    # fetched individually from then on, no more assuming.
    import scraper.browser_manager as browser_manager_module
    original_interval = browser_manager_module.TEAM_RECHECK_INTERVAL
    browser_manager_module.TEAM_RECHECK_INTERVAL = 3
    try:
        bm = BrowserManager()
        fake_rows = [FakeYearRow("Shohei Ohtani", "2024") for _ in range(6)]
        bm._page = FakePage(fake_rows)
        bm.read_row = _read_year_row

        teams_by_fetch_order = ["Los Angeles Angels", "Los Angeles Dodgers",
                                 "Los Angeles Dodgers", "Los Angeles Dodgers"]
        call_log = []

        def fake_fetch(row):
            call_log.append(1)
            return teams_by_fetch_order[len(call_log) - 1]

        bm.fetch_card_details_for_row = lambda row: (fake_fetch(row), "")

        records = bm.read_all_rows(fetch_team=True, sample_team_by_year=True)

        # Row1 fetch, rows2-3 assumed (no fetch), row4 recheck fetch
        # (disagrees -> MIXED), rows5-6 each fetched individually.
        # Total fetches: row1, row4, row5, row6 = 4.
        assert len(call_log) == 4, f"expected 4 fetches, got {len(call_log)}"
        assert [r.team for r in records] == [
            "Los Angeles Angels", "Los Angeles Angels", "Los Angeles Angels",
            "Los Angeles Dodgers", "Los Angeles Dodgers", "Los Angeles Dodgers",
        ]
    finally:
        browser_manager_module.TEAM_RECHECK_INTERVAL = original_interval


def test_year_checkin_keeps_separate_years_independent():
    # A resolved/assumed 2023 must not bleed into a fresh 2024 row -
    # it's a different bucket and needs its own initial check.
    bm = BrowserManager()
    fake_rows = (
        [FakeYearRow("Shohei Ohtani", "2023") for _ in range(2)]
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

    # 1 fetch to establish 2023 (2nd row reuses it) + 1 fetch to
    # establish the brand-new 2024 bucket = 2 total.
    assert len(call_log) == 2
    assert records[0].team == records[1].team == "Los Angeles Angels"
    assert records[2].team == "Los Angeles Dodgers"


class FakeCell:
    def __init__(self, text):
        self._text = text

    def count(self):
        return 1

    def inner_text(self):
        return self._text


class FakeCorrectionRow:
    """Like FakeYearRow but supports .locator() so
    _find_row_by_card_number can relocate it on a re-navigated page."""
    def __init__(self, player_name, year, card_number):
        self.player_name = player_name
        self.year = year
        self.card_number = card_number

    def locator(self, selector):
        return FakeCell(self.card_number)


def test_year_checkin_corrects_pending_rows_retroactively_across_pages():
    # Recheck interval patched to 2. Page 1: card "1" establishes Team A
    # (real fetch), card "2" gets assumed Team A (pending, unresolved).
    # Page 2: card "3" is the recheck row - fetches for real and comes
    # back Team B, disagreeing with the assumption. This must trigger
    # navigating BACK to page 1 to re-fetch card "2" for real (finding
    # out it was actually already Team B), then returning to page 2 to
    # resume forward extraction.
    import scraper.browser_manager as browser_manager_module
    original_interval = browser_manager_module.TEAM_RECHECK_INTERVAL
    browser_manager_module.TEAM_RECHECK_INTERVAL = 2
    try:
        bm = BrowserManager()
        bm.read_row = _read_year_row

        page1_rows = [
            FakeCorrectionRow("Shohei Ohtani", "2024", "1"),
            FakeCorrectionRow("Shohei Ohtani", "2024", "2"),
        ]
        page2_rows = [
            FakeCorrectionRow("Shohei Ohtani", "2024", "3"),
        ]
        pages_by_number = {1: FakePage(page1_rows), 2: FakePage(page2_rows)}
        bm._page = pages_by_number[1]

        # Real team by card_number, as if this is what the site would
        # actually report if asked - card "2" was ALREADY traded, the
        # initial assumption from card "1" just hadn't caught it yet.
        real_team_by_card = {"1": "Los Angeles Angels", "2": "Los Angeles Dodgers", "3": "Los Angeles Dodgers"}
        fetch_log = []

        def fake_fetch(row):
            fetch_log.append(row.card_number)
            return real_team_by_card[row.card_number], ""

        bm.fetch_card_details_for_row = fake_fetch

        nav_log = []

        def fake_navigate_to_page(page_num):
            nav_log.append(page_num)
            bm._page = pages_by_number[page_num]

        bm.navigate_to_page = fake_navigate_to_page
        bm.has_next_page = lambda: bm._current_page_number < 2
        bm.click_next = lambda: fake_navigate_to_page(bm._current_page_number + 1)

        records = bm.extract_all_pages(fetch_team=True, sample_team_by_year=True)

        assert [r.card_number for r in records] == ["1", "2", "3"]
        # Card 1: established directly, correct from the start.
        assert records[0].team == "Los Angeles Angels"
        # Card 2: initially assumed Angels (wrong), then corrected to
        # Dodgers once the recheck on page 2 caught the trade.
        assert records[1].team == "Los Angeles Dodgers"
        # Card 3: the recheck row itself, fetched directly.
        assert records[2].team == "Los Angeles Dodgers"

        # Fetches: card1 (establish), card3 (recheck), card2 (correction) = 3.
        assert sorted(fetch_log) == ["1", "2", "3"], f"unexpected fetch log: {fetch_log}"
        # Correction pass must navigate back to page 1 then forward
        # again to page 2 to resume.
        assert 1 in nav_log and nav_log[-1] == 2, f"unexpected nav log: {nav_log}"
    finally:
        browser_manager_module.TEAM_RECHECK_INTERVAL = original_interval


def test_year_checkin_lettered_variant_rows_are_untouched():
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
    test_year_checkin_fetches_first_row_then_assumes_until_recheck_interval()
    test_year_checkin_switches_to_full_fetch_after_recheck_disagrees()
    test_year_checkin_keeps_separate_years_independent()
    test_year_checkin_corrects_pending_rows_retroactively_across_pages()
    test_year_checkin_lettered_variant_rows_are_untouched()
    print("All tests passed.")
