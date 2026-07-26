"""
BrowserManager

Owns the Playwright browser instance for Checklist Assistant.

Current responsibilities:
    - Launch Chromium
    - Keep the browser alive for the session
    - Keep the active page alive
    - Report the current URL
    - Count rows currently displayed (Phase 1)
    - Read one row / all rows on the current page (Phase 1)
    - Detect and click the Next page button (Phase 2)
    - Read every row across every page (Phase 2)

No other part of the application should talk to Playwright directly.
Everything goes through this class.
"""

from __future__ import annotations

import re

from playwright.sync_api import (
    sync_playwright, Browser, Page, Playwright, Locator,
    TimeoutError as PlaywrightTimeoutError,
)

from scraper.card_record import CardRecord
from settings.selectors import (
    ROW_SELECTOR, FIELD_SELECTORS, PAGINATION_NAV_SELECTOR,
    TEAM_DETAIL_LABEL_SELECTOR, DESCRIPTION_DETAIL_LABEL_SELECTOR,
)
from settings.window_layout import BROWSER_WINDOW_POSITION, BROWSER_WINDOW_SIZE
from settings.extraction_limits import MAX_PAGES, TEAM_RECHECK_INTERVAL
from settings.year_team_cache import MIXED

YEAR_PREFIX_PATTERN = re.compile(r'^\s*(\d{4})')


class BrowserManager:
    """Owns and controls a single Playwright Chromium instance."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        # Maps Name (the raw website text) -> Team, reset at the start
        # of each extract_all_pages() run. Most rows in a set are
        # parallels of the SAME player appearing over and over - this
        # means "Add" only needs to be clicked once per distinct player
        # name, not once per row. Caches a failed lookup (empty string)
        # too, so one bad/slow row doesn't get retried 20 times across
        # all its parallels.
        # Used for Set-mode team fetching (many distinct players).
        self._team_cache: dict[str, str] = {}
        # Used for Player-mode team fetching (one player, potentially
        # thousands of rows across many years). Keyed "name|year" ->
        # see settings/year_team_cache.py for the value states
        # (sampling list / resolved team / MIXED sentinel). Name-keyed
        # caching doesn't work here since every row shares the same
        # player name - caching by name alone would apply one team to
        # a whole career, which is wrong for anyone who changed teams.
        self._year_team_cache: dict[str, list | str] = {}
        # Runtime-only (never persisted to disk, unlike _year_team_cache
        # above): records that were assigned an ASSUMED team since the
        # last real check for their "name|year" key, so that if a later
        # recheck disagrees (see _resolve_team_by_year_checkin), we can
        # go back and fetch each of them for real instead of leaving
        # them on a possibly-wrong assumption. Cleared whenever a key
        # gets a fresh confirmed check (whether the assumption held or
        # broke). Each entry is (CardRecord, page_number_it_was_read_on).
        self._pending_records_by_year: dict[str, list[tuple]] = {}
        # Populated by read_all_rows whenever a key transitions to MIXED
        # during that call; drained by extract_all_pages right after,
        # once it's safely between pages (not mid-row-loop) so it can
        # navigate around to fix the pending records. Reset at the top
        # of every read_all_rows call.
        self._newly_mixed_this_call: dict[str, list[tuple]] = {}
        # Set by extract_all_pages before each read_all_rows call so
        # pending records know which page they were read on.
        self._current_page_number: int = 1

    @property
    def is_launched(self) -> bool:
        return self._browser is not None and self._page is not None

    def launch(self, start_url: str = "https://www.buysportscards.com") -> None:
        """Launch Chromium and navigate to the starting URL.

        Safe to call only once per session. If already launched, this is
        a no-op so the Launch Browser button can be clicked again without
        spawning duplicate browsers.
        """
        if self.is_launched:
            return

        x, y = BROWSER_WINDOW_POSITION
        width, height = BROWSER_WINDOW_SIZE

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=False,
            args=[
                f"--window-position={x},{y}",
                f"--window-size={width},{height}",
            ],
        )
        self._page = self._browser.new_page(viewport=None)
        self._page.goto(start_url)
        self._page.bring_to_front()

    def bring_to_front(self) -> None:
        """Force the automated browser window to the front. Used so
        Brandon can't lose track of which window is actually connected
        to the app - confirmed 2026-07-26 this was the real source of
        repeated 'blank product/sport' reports: he was navigating in a
        completely different (his everyday) Chrome window, not this
        one. Playwright's Chromium is a separate browser install from
        regular Chrome - distinct Dock icon, shows an 'automated test
        software' banner - but that's easy to miss if you're not
        looking for it."""
        if self._page is not None:
            self._page.bring_to_front()

    def current_url(self) -> str | None:
        """Return the URL currently displayed in the browser, if any.

        Waits for the page to finish loading first (best-effort, 5s
        cap) - confirmed 2026-07-26 (Brandon): reading .url while
        Beckett's article page is still mid-navigation (e.g. right
        after clicking Yes on the "navigate and click Yes" prompt) can
        catch a stale/intermediate URL, which makes parse_beckett_url()
        derive nothing and leaves the product/sport prompts blank on
        that run even though the same URL derives correctly once
        settled. A timeout here just means the page didn't fully
        settle in time - falls through to whatever .url already is
        rather than blocking forever."""
        if self._page is None:
            return None
        self._sync_to_latest_page()
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except PlaywrightTimeoutError:
            pass
        return self._page.url

    def _sync_to_latest_page(self) -> None:
        """If a new tab has opened since we last checked (e.g. a site's
        nav menu link uses target="_blank", or a JS window.open() -
        confirmed 2026-07-26 against Beckett's Baseball/Year dropdown
        nav, whose 'View All' links open this way), Chrome auto-
        switches focus to it, so it looks and feels like 'the same
        window' to Brandon even though it's technically a new tab in
        the same BrowserContext. Playwright, left alone, keeps
        _page pointed at the ORIGINAL tab forever - it has no reason to
        follow the new one on its own. This keeps _page pointed at
        whichever tab was most recently opened, which is a reasonable
        proxy for "the one Brandon is actually looking at" since he's
        never intentionally working two tabs at once in this workflow.
        A no-op if there's only one tab open (the common case)."""
        if self._page is None:
            return
        pages = self._page.context.pages
        if pages and pages[-1] is not self._page:
            self._page = pages[-1]

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser is not launched. Click 'Launch Browser' first.")
        self._sync_to_latest_page()
        return self._page

    # ------------------------------------------------------------------
    # Phase 1: read the current page
    # ------------------------------------------------------------------

    def count_rows(self, selector: str = ROW_SELECTOR) -> int:
        """Count the number of rows currently displayed on the page."""
        page = self._require_page()
        return page.locator(selector).count()

    def read_row(self, row: Locator) -> CardRecord:
        """Read a single row element into a raw CardRecord.

        Missing fields are left as empty strings rather than raising, so
        one malformed row doesn't kill the whole extraction.
        """
        values: dict[str, str] = {}
        for field_name, field_selector in FIELD_SELECTORS.items():
            cell = row.locator(field_selector)
            values[field_name] = cell.inner_text().strip() if cell.count() else ""
        return CardRecord(**values)

    def read_all_rows(
        self,
        selector: str = ROW_SELECTOR,
        fetch_team: bool = False,
        pause_callback: callable = None,
        sample_team_by_year: bool = False,
    ) -> list[CardRecord]:
        """Read every row currently displayed on the page.

        If fetch_team is True, also clicks into each row's "Add" page
        to read its Team (BSC doesn't show Team in the table itself -
        only on that detail page), then navigates back before moving to
        the next row. This is MUCH slower (one extra page visit per
        row) and was confirmed safe (clicking "Add" only opens BSC's
        listing-creation form, it doesn't submit or create anything -
        confirmed by Brandon clicking through it manually first) but
        should be used deliberately, not as a default - see the
        fetch_team prompt in app/main_window.py.

        Team lookups are cached per distinct Name text for the whole
        extraction run (see self._team_cache) - most rows in a set are
        parallels of the same player, so this avoids re-clicking "Add"
        for every single parallel of a player already looked up. This
        is the Set-mode strategy (many distinct players).

        sample_team_by_year switches to the Player-mode strategy
        instead (one player, potentially tens of thousands of rows): a
        name-keyed cache is useless here since every row shares the
        same player name. Instead: fetch the team for the FIRST
        non-lettered row of each distinct year and assume that team for
        the rest of the year. Every TEAM_RECHECK_INTERVAL non-lettered
        rows after that, fetch again to confirm the assumption still
        holds. If the recheck still matches, keep assuming (and reset
        the counter). If it doesn't, a trade happened that year - every
        remaining row for that year gets fetched individually from that
        point on, since we can't tell which side of the trade any given
        row falls on without checking. This turns a potential
        50,000-row player pull into roughly (distinct years x a few
        fetches) in the common case, only paying the full per-row cost
        for years that actually had a trade - and unlike a single
        upfront sample, it catches a trade no matter where in the year
        it happened, not just one visible in the first few cards. See
        settings/year_team_cache.py for the cache's on-disk format.

        When a recheck disagrees with the assumption, every row that
        was assigned the (now known wrong) assumed team since the last
        real check gets corrected retroactively - see
        extract_all_pages, which drives this once the current page is
        fully read (navigating around mid-row-loop here would break
        this method's own row indexing). This does mean a confirmed
        trade costs roughly one extra fetch per previously-assumed row
        in that window (up to TEAM_RECHECK_INTERVAL - 1 of them) - a
        real cost, but paid only for years that actually had a trade,
        same as the rest of this strategy. Rows from a PRIOR app
        session (before a restart) can't be corrected this way, since
        their CardRecord objects are gone by the time the app restarts
        - only self._year_team_cache's {team, count_since_check} state
        persists to disk, not the pending-records list itself.

        pause_callback, if provided, is called after every team fetch so
        the extraction can be paused mid-page without waiting for a full
        page turn to finish.
        """
        page = self._require_page()
        self._newly_mixed_this_call = {}
        records: list[CardRecord] = []
        rows = page.locator(selector)
        count = rows.count()

        for i in range(count):
            row = page.locator(selector).nth(i)
            record = self.read_row(row)

            # Lettered card numbers (e.g. #1b, #1c) ALWAYS get their
            # details fetched - we need the description to build the
            # parallel name. Team is read at the same time as a bonus.
            # Non-lettered rows only visit the Add page when fetch_team
            # is on (and only on a cache miss).
            raw_num = record.card_number.lstrip("#").strip()
            is_letter_variant = bool(re.match(r'^\d+[a-z]$', raw_num))

            needs_fetch = is_letter_variant or fetch_team
            if needs_fetch:
                if sample_team_by_year and not is_letter_variant:
                    self._resolve_team_by_year_checkin(record, row, pause_callback)
                elif not is_letter_variant and record.name in self._team_cache:
                    # Non-lettered cache hit - skip the page visit.
                    record.team = self._team_cache[record.name]
                else:
                    team, description = self.fetch_card_details_for_row(row)
                    record.description = description
                    record.team = team
                    if record.name and not is_letter_variant:
                        # Only cache team by player name for non-lettered
                        # rows - lettered rows may share a player name but
                        # have different descriptions, so they're never
                        # served from this cache.
                        self._team_cache[record.name] = team
                    if pause_callback:
                        pause_callback()
            records.append(record)

        return records

    def _year_bucket(self, set_text: str) -> str:
        """Leading 4-digit year from a raw Set string, or 'unknown' if
        none is found. Same rule Phase 5 (exporter/convert.py) applies
        later for the real Year column - this is just an earlier, rough
        version of it used only to group rows for team sampling."""
        match = YEAR_PREFIX_PATTERN.match(set_text or "")
        return match.group(1) if match else "unknown"

    def _resolve_team_by_year_checkin(
        self, record: CardRecord, row: Locator, pause_callback: callable = None
    ) -> None:
        """Player-mode team resolution for one non-lettered row - see
        read_all_rows' sample_team_by_year docstring for the full
        strategy. Mutates record.team in place.

        Records assigned an ASSUMED (not directly fetched) team are
        tracked in self._pending_records_by_year so that if a later
        recheck disagrees, extract_all_pages can go back and fetch each
        of them for real - see _correct_pending_records. This method
        itself never navigates anywhere other than the current row's
        Add page (mid-page-loop navigation would break the row-index
        loop in read_all_rows) - it only flags the correction via
        self._newly_mixed_this_call for extract_all_pages to act on
        once it's safely between pages.
        """
        year = self._year_bucket(record.set)
        key = f"{record.name}|{year}"
        state = self._year_team_cache.get(key)

        if state == MIXED:
            # Already confirmed mixed this year - every row gets its own
            # real fetch, no assumption, cache untouched further.
            team, description = self.fetch_card_details_for_row(row)
            record.team = team
            record.description = description
            if pause_callback:
                pause_callback()
            return

        if state is None:
            # First row seen for this player/year - establish the
            # assumption. This row itself is a real fetch, not pending.
            team, description = self.fetch_card_details_for_row(row)
            record.team = team
            record.description = description
            if pause_callback:
                pause_callback()
            self._year_team_cache[key] = {"team": team, "count_since_check": 0}
            self._pending_records_by_year[key] = []
            return

        # state is {"team": ..., "count_since_check": ...} - still
        # assuming. Bump the counter; only fetch for real once the
        # recheck interval is hit.
        count_since_check = state["count_since_check"] + 1
        if count_since_check < TEAM_RECHECK_INTERVAL:
            record.team = state["team"]
            self._pending_records_by_year.setdefault(key, []).append((record, self._current_page_number))
            self._year_team_cache[key] = {"team": state["team"], "count_since_check": count_since_check}
            return

        # Recheck row: fetch for real and compare against the assumption.
        team, description = self.fetch_card_details_for_row(row)
        record.team = team
        record.description = description
        if pause_callback:
            pause_callback()

        if team == state["team"]:
            # Assumption held - every pending row in between was right
            # all along, nothing to correct.
            self._year_team_cache[key] = {"team": team, "count_since_check": 0}
            self._pending_records_by_year[key] = []
        else:
            # Assumption broke - a trade happened somewhere in this
            # window. Flag the pending rows for a real recheck rather
            # than leaving them on the old (possibly wrong) team.
            pending = self._pending_records_by_year.get(key, [])
            if pending:
                self._newly_mixed_this_call[key] = pending
            self._pending_records_by_year[key] = []
            self._year_team_cache[key] = MIXED

    def _find_row_by_card_number(self, card_number: str, selector: str = ROW_SELECTOR) -> Locator | None:
        """Search the currently-displayed page for a row whose Card #
        matches, for relocating a specific card after navigating back
        to an earlier page. Returns the first match, or None. Matching
        on card_number alone is safe for team-correction purposes even
        if multiple rows share it (different parallels of the same
        card) - every parallel of the same physical card has the same
        Team, so any matching row gives the right answer."""
        page = self._require_page()
        rows = page.locator(selector)
        count = rows.count()
        target = card_number.lstrip("#").strip()
        for i in range(count):
            row = rows.nth(i)
            cell = row.locator(FIELD_SELECTORS["card_number"])
            text = cell.inner_text().strip().lstrip("#").strip() if cell.count() else ""
            if text == target:
                return row
        return None

    def _correct_pending_records(
        self, pending: list[tuple], resume_page: int, pause_callback: callable = None, on_status: callable = None,
    ) -> None:
        """Go back and fetch the REAL team for each (record, page_number)
        in `pending`, mutating each record.team in place, then navigate
        back to resume_page so forward extraction can continue exactly
        where it left off. Called by extract_all_pages right after a
        read_all_rows call reports a fresh MIXED transition via
        self._newly_mixed_this_call - never mid-row-loop.

        Best-effort: if a pending card can't be relocated on its
        original page (rare - would need the page's row order/contents
        to have changed since it was first read), that record is left
        on its old assumed team rather than raising, since one
        unfindable row shouldn't abort the whole correction pass.
        """
        by_page: dict[int, list] = {}
        for record, page_number in pending:
            by_page.setdefault(page_number, []).append(record)

        for page_number in sorted(by_page.keys()):
            if on_status:
                on_status(f"Trade detected — rechecking {len(by_page[page_number])} card(s) on page {page_number}…")
            self.navigate_to_page(page_number)
            for record in by_page[page_number]:
                found_row = self._find_row_by_card_number(record.card_number)
                if found_row is None:
                    continue
                team, _description = self.fetch_card_details_for_row(found_row)
                record.team = team
                if pause_callback:
                    pause_callback()

        self.navigate_to_page(resume_page)

    def fetch_card_details_for_row(self, row: Locator) -> tuple[str, str]:
        """Click this row's "Add" control, read Team and Description off
        the resulting detail page, then navigate back.
        Returns (team, description) - either may be "" if not found.
        Never raises, so one bad row doesn't kill the whole extraction.
        """
        page = self._require_page()
        add_control = row.get_by_role("button", name="Add", exact=True)
        if add_control.count() == 0:
            return "", ""

        add_control.first.click()
        try:
            page.wait_for_selector(TEAM_DETAIL_LABEL_SELECTOR, timeout=15000)
            team = self.read_detail_field(TEAM_DETAIL_LABEL_SELECTOR)
            description = self.read_detail_field(DESCRIPTION_DETAIL_LABEL_SELECTOR)
        except Exception:
            team, description = "", ""
        finally:
            page.go_back()
            page.wait_for_selector(ROW_SELECTOR, timeout=15000)
            page.wait_for_timeout(300)

        return team, description

    def read_detail_field(self, label_selector: str) -> str:
        """Read a labelled field value from the Sell-Your-Card detail
        page. Label and value sit in two sibling <div>s; the value is
        the <h6> inside the label's next sibling div."""
        page = self._require_page()
        label = page.locator(label_selector)
        if label.count() == 0:
            return ""
        value = label.locator("xpath=../following-sibling::div[1]//h6")
        if value.count() == 0:
            return ""
        return value.first.inner_text().strip()

    # ------------------------------------------------------------------
    # Phase 2: read all pages
    # ------------------------------------------------------------------
    #
    # BuySportsCards' pagination is a numbered page list (1, 2, 3 ... N)
    # inside a single <nav>. The prev/next arrow icons at each end are
    # NOT real <button> elements (just <p><svg>), so they can't be
    # reliably clicked or checked for a disabled state. Instead, find the
    # currently active page via [aria-current="true"] and click the
    # button for current+1. Confirmed working against the live site.

    def _pagination_status(self, nav_selector: str = PAGINATION_NAV_SELECTOR) -> tuple[int | None, int]:
        """Return (current_page, highest_page_number_visible).

        highest_page_number_visible is the largest numbered button found
        in the nav at this moment. BuySportsCards keeps the last page
        number visible in the sliding window, so this is the true total
        page count in practice - not just whatever's currently rendered.
        """
        page = self._require_page()
        nav = page.locator(nav_selector)
        buttons = nav.locator("button")
        count = buttons.count()

        current: int | None = None
        highest = 0
        for i in range(count):
            button = buttons.nth(i)
            text = button.inner_text().strip().replace(",", "")  # "1,000" -> "1000"
            if text.isdigit():
                num = int(text)
                highest = max(highest, num)
                if button.get_attribute("aria-current") == "true":
                    current = num
        return current, highest

    def has_next_page(self, nav_selector: str = PAGINATION_NAV_SELECTOR) -> bool:
        current, highest = self._pagination_status(nav_selector)
        if current is None:
            return False
        return current < highest

    def click_next(
        self,
        nav_selector: str = PAGINATION_NAV_SELECTOR,
        row_selector: str = ROW_SELECTOR,
    ) -> None:
        """Advance to the next page. Tries the numbered button first; if
        it's hidden in BSC's sliding-window ellipsis, falls back to URL
        navigation so a run never stalls mid-set."""
        page = self._require_page()
        current, _ = self._pagination_status(nav_selector)
        if current is None:
            raise RuntimeError("Could not determine current page from pagination nav.")

        next_page = current + 1

        # Try the numbered button first (fast, no page reload).
        nav = page.locator(nav_selector)
        buttons = nav.locator("button")
        count = buttons.count()
        for i in range(count):
            button = buttons.nth(i)
            if button.inner_text().strip().replace(",", "") == str(next_page):
                button.click()
                page.wait_for_timeout(500)
                page.wait_for_selector(row_selector)
                return

        # Button not visible (hidden in BSC's "..." ellipsis) - navigate
        # via URL instead, same as navigate_to_page does.
        current_url = page.url
        url_match = re.search(r'(?<=[?&])p=\d+', current_url)
        if url_match:
            new_url = (
                current_url[:url_match.start()]
                + f"p={next_page}"
                + current_url[url_match.end():]
            )
            page.goto(new_url)
            page.wait_for_selector(row_selector, timeout=15000)
            page.wait_for_timeout(300)
            return

        raise RuntimeError(
            f"Could not advance to page {next_page}: button not visible "
            f"and URL has no p= parameter to modify."
        )

    def navigate_to_page(
        self,
        target: int,
        nav_selector: str = PAGINATION_NAV_SELECTOR,
        row_selector: str = ROW_SELECTOR,
    ) -> None:
        """Navigate to a specific page number.

        Strategy (tried in order):
        1. Already there - return immediately.
        2. URL parameter - if the current URL has a 'page=' parameter,
           replace its value and navigate directly. Most reliable.
        3. Pagination button - if a button for the target page is visible
           in BSC's sliding nav window, click it.
        4. Sequential Next - click Next one step at a time until the
           target page button becomes visible, then click it. Works from
           any starting position but is slow for large jumps.
        """
        page = self._require_page()
        current, _ = self._pagination_status(nav_selector)
        if current == target:
            return

        # --- Strategy 2: URL parameter ---
        # BSC uses 'p=N' (not 'page=N') as the pagination query param.
        # Match it only when preceded by '?' or '&' so we don't
        # accidentally clobber a param like 'sport=' or 'setName[]='.
        current_url = page.url
        url_match = re.search(r'(?<=[?&])p=\d+', current_url)
        if url_match:
            new_url = current_url[:url_match.start()] + f"p={target}" + current_url[url_match.end():]
            page.goto(new_url)
            page.wait_for_selector(row_selector, timeout=15000)
            page.wait_for_timeout(300)
            return

        # --- Strategy 3: Pagination button visible right now ---
        def try_button() -> bool:
            nav = page.locator(nav_selector)
            buttons = nav.locator("button")
            count = buttons.count()
            for i in range(count):
                button = buttons.nth(i)
                if button.inner_text().strip().replace(",", "") == str(target):
                    button.click()
                    page.wait_for_timeout(500)
                    page.wait_for_selector(row_selector)
                    return True
            return False

        if try_button():
            return

        # --- Strategy 4: Sequential Next until target button appears ---
        for _ in range(MAX_PAGES):
            cur, _ = self._pagination_status(nav_selector)
            if cur is not None and cur >= target:
                return  # overshot or landed on it
            if try_button():
                return
            if not self.has_next_page():
                break
            self.click_next()
            page.wait_for_timeout(300)

        raise RuntimeError(
            f"Could not navigate to page {target}. "
            f"Current URL has no 'page=' parameter and the sequential "
            f"nav search exhausted all pages."
        )

    def extract_all_pages(
        self,
        max_pages: int = MAX_PAGES,
        fetch_team: bool = False,
        pause_callback: callable = None,
        start_page: int = 1,
        end_page: int = 0,
        on_status: callable = None,
        sample_team_by_year: bool = False,
    ) -> list[CardRecord]:
        """Read every row across a range of pages.

        start_page: first page to scrape (1-based). If > 1 the browser
            navigates to that page first by clicking its number in the
            pagination nav.
        end_page: last page to scrape, inclusive. 0 (default) means
            scrape until the last page.
        max_pages: hard safety cap on total pages visited regardless of
            end_page, so a bug can't spin forever.
        fetch_team: see read_all_rows docstring.
        sample_team_by_year: see read_all_rows docstring - Player-mode
            team-fetching strategy, mutually exclusive in practice with
            the Set-mode name-keyed cache (only one strategy is used
            per run, chosen by the caller based on checklist type).
            When a recheck discovers a trade mid-year, this method
            (not read_all_rows itself) drives the retroactive
            correction pass right after that page finishes reading -
            navigating back to fix the pending rows requires being
            between pages, not mid-row-loop. See
            _correct_pending_records and the newly_mixed_this_call
            comment on __init__.
        pause_callback: called between every team fetch and every page
            turn so the run can be paused mid-scrape.
        """
        # Team cache(s) are loaded from disk by the caller
        # (ExtractionWorker) before this method is invoked, so they
        # already contain any lookups from previous runs. Do NOT reset
        # either cache here.

        if start_page > 1:
            if on_status:
                on_status(f"Navigating to page {start_page}…")
            self.navigate_to_page(start_page)

        all_records: list[CardRecord] = []
        current_page = start_page
        pages_visited = 0

        while True:
            if on_status:
                on_status(f"Reading page {current_page}… ({len(all_records):,} rows so far)")

            self._current_page_number = current_page
            page_records = self.read_all_rows(
                fetch_team=fetch_team,
                pause_callback=pause_callback,
                sample_team_by_year=sample_team_by_year,
            )
            all_records.extend(page_records)
            pages_visited += 1

            if sample_team_by_year and self._newly_mixed_this_call:
                # Safe to navigate around here - this page's row loop
                # has fully finished and click_next() hasn't happened
                # yet, so navigating back to earlier pages to correct
                # pending records and then back to current_page leaves
                # forward pagination exactly where it would otherwise be.
                for pending in self._newly_mixed_this_call.values():
                    self._correct_pending_records(
                        pending, resume_page=current_page,
                        pause_callback=pause_callback, on_status=on_status,
                    )
                self._newly_mixed_this_call = {}

            if on_status:
                on_status(f"Page {current_page}: {len(page_records)} rows — {len(all_records):,} total")

            at_end_page = end_page > 0 and current_page >= end_page
            at_last_page = not self.has_next_page()
            at_cap = pages_visited >= max_pages

            if at_end_page or at_last_page or at_cap:
                break

            self.click_next()
            current_page += 1
            if pause_callback:
                pause_callback()

        return all_records

    # ------------------------------------------------------------------
    # Multi-source support (Beckett, TCDB) - added 2026-07-04
    #
    # Unlike BSC, these sites need no login and no per-row DOM
    # interaction (Team fetching, pagination clicking). The app just
    # needs to: navigate to wherever Brandon already is, optionally
    # trigger one UI action (Beckett's "Full Checklist" tab), and read
    # back the resulting HTML for the appropriate parser
    # (parsers/beckett_parser.py, parsers/tcdb_parser.py) to handle.
    #
    # NOT YET CONFIRMED against the live sites - the click selector for
    # Beckett's "Full Checklist" tab is built from the real HTML Brandon
    # provided during development, but hasn't been run against a live
    # browser session. Treat the first real run as the actual test and
    # report back exactly what happens (or the DOM around it) if it
    # doesn't click the right thing - same as any other selector in
    # this file.
    # ------------------------------------------------------------------

    def navigate_to_url(self, url: str) -> None:
        """Navigate the already-launched browser to an arbitrary URL.
        Unlike launch(), this works after the browser is already open -
        use this to move between BSC/Beckett/TCDB within one session."""
        page = self._require_page()
        page.goto(url)

    def get_page_html(self, selector: str | None = None) -> str:
        """Return the current page's HTML. If selector is given,
        return just that element's outerHTML instead of the whole
        page (faster to parse, avoids irrelevant page chrome)."""
        page = self._require_page()
        if selector:
            return page.locator(selector).first.evaluate("el => el.outerHTML")
        return page.content()

    def click_beckett_full_checklist(self) -> str:
        """Click Beckett's 'Full Checklist' tab and return that tab
        panel's HTML.

        Primary strategy (confirmed 2026-07-26 against the live 2026
        Topps Pristine Baseball page, DOM-inspected directly): this is
        the "Advanced Gutenberg" WordPress tabs plugin, used site-wide
        for Beckett checklist articles. Its aria-controls attribute is
        broken/decorative - it points to near-empty placeholder
        elements (just the tab's own label text, not real content),
        NOT the real content. The actual association between a tab
        button and its content is purely POSITIONAL: the Nth tab
        button (role="tab", in DOM order) corresponds to the Nth
        ".advgb-tab-body" element (also in DOM order) within the same
        ".advgb-tabs-wrapper" container. Every tab's content already
        exists in the DOM regardless of which is visually active (they
        differ only by inline display:none) - clicking isn't strictly
        required to read the content, but is still done first for
        consistency/safety in case some article's markup genuinely
        needs it.

        Fallback strategy: the original <a><strong> structure this was
        first built against (from a hand-provided HTML snippet, never
        actually confirmed live before 2026-07-26). Kept as a defensive
        second attempt in case some article uses a different/older
        tabs structure entirely - costs nothing since .count() checks
        avoid waiting out the full auto-wait timeout on a pattern that
        isn't present (the bug that caused the original 30s timeout).
        """
        page = self._require_page()

        wrapper = page.locator(".advgb-tabs-wrapper").first
        if wrapper.count() > 0:
            tabs = wrapper.locator('[role="tab"]')
            bodies = wrapper.locator(".advgb-tab-body")
            tab_count = tabs.count()
            body_count = bodies.count()
            for i in range(tab_count):
                if tabs.nth(i).inner_text().strip() == "Full Checklist":
                    tabs.nth(i).click()
                    if i < body_count:
                        return bodies.nth(i).evaluate("el => el.outerHTML")
                    break

        tab_link = page.locator("a", has=page.locator("strong", has_text="Full Checklist")).first
        if tab_link.count() > 0:
            href = tab_link.get_attribute("href") or ""
            panel_id = href.lstrip("#")
            tab_link.click()
            if panel_id:
                panel_selector = f"#{panel_id}, div[aria-labelledby='{panel_id}']"
                return page.locator(panel_selector).first.evaluate("el => el.outerHTML")

        # Last resort - report the whole page rather than crash, so
        # the parser at least has something to work with and Brandon
        # can tell us what actually happened.
        return page.content()

    def close(self) -> None:
        """Close the browser and stop Playwright cleanly."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None
