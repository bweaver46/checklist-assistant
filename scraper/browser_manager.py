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

from playwright.sync_api import sync_playwright, Browser, Page, Playwright, Locator

from scraper.card_record import CardRecord
from settings.selectors import (
    ROW_SELECTOR, FIELD_SELECTORS, PAGINATION_NAV_SELECTOR,
    TEAM_DETAIL_LABEL_SELECTOR, DESCRIPTION_DETAIL_LABEL_SELECTOR,
)
from settings.window_layout import BROWSER_WINDOW_POSITION, BROWSER_WINDOW_SIZE
from settings.extraction_limits import MAX_PAGES


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
        self._team_cache: dict[str, str] = {}

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

    def current_url(self) -> str | None:
        """Return the URL currently displayed in the browser, if any."""
        if self._page is None:
            return None
        return self._page.url

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser is not launched. Click 'Launch Browser' first.")
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
        for every single parallel of a player already looked up.

        pause_callback, if provided, is called after every team fetch so
        the extraction can be paused mid-page without waiting for a full
        page turn to finish.
        """
        page = self._require_page()
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
                if not is_letter_variant and record.name in self._team_cache:
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
        pause_callback: called between every team fetch and every page
            turn so the run can be paused mid-scrape.
        """
        # Team cache is loaded from disk by the caller (ExtractionWorker)
        # before this method is invoked, so it already contains any
        # lookups from previous runs. Do NOT reset it here.

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

            page_records = self.read_all_rows(
                fetch_team=fetch_team,
                pause_callback=pause_callback,
            )
            all_records.extend(page_records)
            pages_visited += 1

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
        panel's HTML. Finds the tab panel by following the tab link's
        own href (e.g. '#advgb-tabs-tab4') rather than hardcoding a tab
        number, since that number isn't guaranteed to be the same
        across different Beckett articles."""
        page = self._require_page()
        tab_link = page.locator("a", has=page.locator("strong", has_text="Full Checklist")).first
        href = tab_link.get_attribute("href") or ""
        panel_id = href.lstrip("#")
        tab_link.click()
        if panel_id:
            panel_selector = f"#{panel_id}, div[aria-labelledby='{panel_id}']"
            return page.locator(panel_selector).first.evaluate("el => el.outerHTML")
        # Fallback if the href-based lookup ever fails on a differently
        # structured page - report the whole page rather than crash, so
        # the parser at least has something to work with and Brandon can
        # tell us what actually happened.
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
