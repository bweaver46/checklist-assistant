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
from settings.selectors import ROW_SELECTOR, FIELD_SELECTORS, NEXT_BUTTON_SELECTOR


class BrowserManager:
    """Owns and controls a single Playwright Chromium instance."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

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

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=False)
        self._page = self._browser.new_page()
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

    def read_all_rows(self, selector: str = ROW_SELECTOR) -> list[CardRecord]:
        """Read every row currently displayed on the page."""
        page = self._require_page()
        rows = page.locator(selector)
        count = rows.count()
        return [self.read_row(rows.nth(i)) for i in range(count)]

    # ------------------------------------------------------------------
    # Phase 2: read all pages
    # ------------------------------------------------------------------

    def has_next_page(self, next_selector: str = NEXT_BUTTON_SELECTOR) -> bool:
        """Return True if a Next button exists and is enabled/clickable."""
        page = self._require_page()
        next_button = page.locator(next_selector)
        if next_button.count() == 0:
            return False
        return next_button.is_enabled()

    def click_next(
        self,
        next_selector: str = NEXT_BUTTON_SELECTOR,
        row_selector: str = ROW_SELECTOR,
    ) -> None:
        """Click Next and wait for the table to reload.

        NOTE: this wait strategy is a best guess (settle delay + wait for
        rows to be present again). If BuySportsCards' pagination is a full
        page navigation rather than an AJAX refresh, or vice versa, this
        may need to switch to page.wait_for_load_state() or wait for a
        specific row's text to change. Validate against the live site.
        """
        page = self._require_page()
        page.locator(next_selector).click()
        page.wait_for_timeout(500)
        page.wait_for_selector(row_selector)

    def extract_all_pages(self, max_pages: int = 200) -> list[CardRecord]:
        """Read every row across every page until Next is exhausted.

        max_pages is a safety cap so a pagination-detection bug can't
        spin forever against the live site.
        """
        all_records: list[CardRecord] = []
        page_num = 1
        while True:
            all_records.extend(self.read_all_rows())
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
