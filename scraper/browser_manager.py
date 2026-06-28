"""
BrowserManager

Owns the Playwright browser instance for Checklist Assistant.

Responsibilities (current):
    - Launch Chromium
    - Keep the browser alive for the session
    - Keep the active page alive
    - Report the current URL
    - Count rows currently displayed on the page (v0.0.2 milestone)

Responsibilities (planned):
    - Read row data
    - Click "Next" / paginate
    - Extract card information into structured records

No other part of the application should talk to Playwright directly.
Everything goes through this class.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright, Browser, Page, Playwright


# Default selector for inventory rows on BuySportsCards.
# This is intentionally a setting, not a hardcoded constant, because
# the real selector should be confirmed against the live site and may
# change. Update via settings, or override when calling count_rows().
DEFAULT_ROW_SELECTOR = "table tbody tr"


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

        Safe to call only once per session. If already launched,
        this is a no-op so the Launch Browser button can be clicked
        again without spawning duplicate browsers.
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

    def count_rows(self, selector: str = DEFAULT_ROW_SELECTOR) -> int:
        """Count the number of rows currently displayed on the page.

        This is the v0.0.2 milestone: proof that Checklist Assistant
        can "see" the page. It deliberately does nothing beyond counting.

        Raises:
            RuntimeError: if the browser has not been launched yet.
        """
        if self._page is None:
            raise RuntimeError("Browser is not launched. Click 'Launch Browser' first.")

        return self._page.locator(selector).count()

    def close(self) -> None:
        """Close the browser and stop Playwright cleanly."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None
