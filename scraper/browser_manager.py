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

from playwright.sync_api import sync_playwright, Browser, Page, Playwright, Locator

from scraper.card_record import CardRecord
from settings.selectors import (
    ROW_SELECTOR, FIELD_SELECTORS, PAGINATION_NAV_SELECTOR, TEAM_DETAIL_LABEL_SELECTOR,
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

    def read_all_rows(self, selector: str = ROW_SELECTOR, fetch_team: bool = False) -> list[CardRecord]:
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
        """
        page = self._require_page()
        records: list[CardRecord] = []
        rows = page.locator(selector)
        count = rows.count()

        for i in range(count):
            # Re-query fresh each time: after navigating away to the
            # detail page and back, the original `rows` handle may be
            # stale even though Brandon confirmed Back restores the
            # exact same page/scroll state.
            row = page.locator(selector).nth(i)
            record = self.read_row(row)
            if fetch_team:
                if record.name in self._team_cache:
                    record.team = self._team_cache[record.name]
                else:
                    team = self.fetch_team_for_row(row)
                    record.team = team
                    if record.name:
                        self._team_cache[record.name] = team
            records.append(record)

        return records

    def fetch_team_for_row(self, row: Locator) -> str:
        """Click this row's "Add" control, read Team off the resulting
        detail page, then navigate back. Returns "" if anything about
        this row's Add control or the Team field can't be found -
        never raises, so one bad row doesn't kill the whole extraction.
        """
        page = self._require_page()
        add_control = row.get_by_role("button", name="Add", exact=True)
        if add_control.count() == 0:
            return ""

        add_control.first.click()
        try:
            page.wait_for_selector(TEAM_DETAIL_LABEL_SELECTOR, timeout=15000)
            team = self.read_team_from_detail_page()
        except Exception:
            team = ""
        finally:
            page.go_back()
            page.wait_for_selector(ROW_SELECTOR, timeout=15000)
            page.wait_for_timeout(300)  # brief politeness delay between rows

        return team

    def read_team_from_detail_page(self) -> str:
        """Team's label ('Team:') and value sit in two sibling <div>s on
        the Sell-Your-Card detail page - the value is the only <h6>
        inside the label's next sibling div."""
        page = self._require_page()
        label = page.locator(TEAM_DETAIL_LABEL_SELECTOR)
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
            text = button.inner_text().strip()
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
        """Click the button for current_page + 1 and wait for the table to reload."""
        page = self._require_page()
        current, _ = self._pagination_status(nav_selector)
        if current is None:
            raise RuntimeError("Could not determine current page from pagination nav.")

        next_page = current + 1
        nav = page.locator(nav_selector)
        buttons = nav.locator("button")
        count = buttons.count()
        for i in range(count):
            button = buttons.nth(i)
            if button.inner_text().strip() == str(next_page):
                button.click()
                break
        else:
            raise RuntimeError(f"Could not find a page button for page {next_page}.")

        page.wait_for_timeout(500)
        page.wait_for_selector(row_selector)

    def extract_all_pages(self, max_pages: int = MAX_PAGES, fetch_team: bool = False) -> list[CardRecord]:
        """Read every row across every page until Next is exhausted.

        max_pages is a safety cap so a pagination-detection bug can't
        spin forever against the live site. fetch_team is passed
        through to read_all_rows - see its docstring for the real cost
        of turning this on. The per-player team cache is reset here, at
        the start of each fresh extraction run, so a new search never
        reuses team data left over from a previous one.
        """
        if fetch_team:
            self._team_cache = {}

        all_records: list[CardRecord] = []
        page_num = 1
        while True:
            all_records.extend(self.read_all_rows(fetch_team=fetch_team))
            if not self.has_next_page() or page_num >= max_pages:
                break
            self.click_next()
            page_num += 1
        return all_records

    def close(self) -> None:
        """Close the browser and stop Playwright cleanly."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None
