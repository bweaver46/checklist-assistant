"""
ExtractionWorker

Runs the extraction pipeline on the MAIN thread (no QThread) to satisfy
Playwright's requirement that all sync API calls happen on the thread
where sync_playwright().start() was called.

The pause_callback passed into browser_manager calls
QApplication.processEvents() on every invocation so the UI stays alive
during the scraping loop. If the user clicked Pause, the callback spins
in a processEvents() loop until Resume is clicked.

The worker is a plain class, not a QThread. MainWindow calls run()
directly and updates the UI itself via the progress/status signals
pattern (replaced here with direct statusBar calls via a provided
callback).
"""

from __future__ import annotations

import time

from PySide6.QtWidgets import QApplication

from scraper.browser_manager import BrowserManager
from exporter.raw_export import write_raw_csv
from exporter.convert import convert_all
from exporter.merge import build_checklist_rows
from exporter.cleanup import apply_cleanup
from exporter.final_export import write_final_csv, sort_rows_by_brand
from settings.accumulator import load_accumulated, save_accumulated
from settings.team_cache import load_team_cache, save_team_cache
from settings.year_team_cache import load_year_team_cache, save_year_team_cache
from settings.output_naming import raw_export_path, final_export_path, DEFAULT_NAME


class ExtractionWorker:
    """Runs the full extraction pipeline synchronously on the main thread.

    pause() / resume() are called from button click handlers (which fire
    during QApplication.processEvents() calls inside the pause_callback).
    """

    def __init__(
        self,
        browser_manager: BrowserManager,
        context: dict,
        on_progress,   # callable(str) -> None
        on_finished,   # callable(int, int, int, str) -> None
        on_error,      # callable(str) -> None
        on_paused,     # callable() -> None
        on_resumed,    # callable() -> None
    ) -> None:
        self._browser_manager = browser_manager
        self._context = context
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_paused = on_paused
        self._on_resumed = on_resumed
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def _pause_callback(self) -> None:
        """Called between every team fetch and every page turn.
        Processes Qt events to keep the UI alive. If paused, spins here
        until resume() is called via a button click processed in the loop.
        """
        QApplication.processEvents()
        if self._paused:
            self._on_paused()
            while self._paused:
                QApplication.processEvents()
                time.sleep(0.05)   # avoid burning the CPU while waiting
            self._on_resumed()

    def run(self) -> None:
        try:
            fetch_team = self._context.get("fetch_team", False)
            start_page = self._context.get("start_page", 1)
            end_page = self._context.get("end_page", 0)
            # Player mode uses year-bucket sampling instead of the
            # Set-mode name-keyed cache - see BrowserManager.read_all_rows
            # and settings/year_team_cache.py for why (a name-keyed cache
            # is useless when every row shares the same player name).
            sample_team_by_year = fetch_team and self._context.get("checklist_type") == "Player"

            if fetch_team and not sample_team_by_year:
                # Merge the disk cache into whatever is already in memory.
                # The BrowserManager instance lives for the whole app session,
                # so its _team_cache already contains everything from prior
                # runs within this session. Disk fills in any gaps (e.g. after
                # an app restart). In-memory always takes priority over disk so
                # a failed/empty save never wipes a working in-memory cache.
                disk_cache = load_team_cache()
                merged = {**disk_cache, **self._browser_manager._team_cache}
                self._browser_manager._team_cache = merged
                cached_count = len(merged)
                if cached_count:
                    self._on_progress(
                        f"Loaded {cached_count:,} cached team lookups — scraping…"
                    )
            elif sample_team_by_year:
                disk_cache = load_year_team_cache()
                merged = {**disk_cache, **self._browser_manager._year_team_cache}
                self._browser_manager._year_team_cache = merged
                cached_years = len(merged)
                if cached_years:
                    self._on_progress(
                        f"Loaded {cached_years:,} cached player/year team lookups — scraping…"
                    )

            page_desc = (
                f"pages {start_page}–{end_page}" if end_page
                else f"page {start_page} onwards"
            )
            self._on_progress(f"Scraping {page_desc}…")

            new_records = self._browser_manager.extract_all_pages(
                fetch_team=fetch_team,
                pause_callback=self._pause_callback,
                start_page=start_page,
                end_page=end_page,
                on_status=self._on_progress,
                sample_team_by_year=sample_team_by_year,
            )

            if fetch_team and not sample_team_by_year:
                save_team_cache(self._browser_manager._team_cache)
            elif sample_team_by_year:
                save_year_team_cache(self._browser_manager._year_team_cache)

            prior_records = load_accumulated()
            all_records = prior_records + new_records

            # Deduplicate raw rows so overlapping page ranges (e.g. re-running
            # page 999 to make sure it completed) don't produce duplicate card
            # rows in the final CSV. Key is the full field tuple - two rows are
            # only duplicates if every field matches exactly.
            seen: set[tuple] = set()
            deduped: list = []
            for r in all_records:
                key = (r.name, r.card_number, r.set, r.variant, r.variant_name, r.attributes)
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            all_records = deduped

            save_accumulated(all_records)

            self._on_progress(
                f"+{len(new_records):,} new rows "
                f"({len(prior_records):,} prior + {len(new_records):,} this run "
                f"= {len(all_records):,} total) — building checklist…"
            )
            QApplication.processEvents()

            # output_name was already resolved to a unique, sanitized
            # name when the user was prompted (see main_window._prompt_for_context).
            # Every page-range chunk of the SAME set reuses this exact
            # name (persisted in the context/last_run), so chunks keep
            # rebuilding the same pair of files as intended. Starting a
            # genuinely new set always goes through that prompt again
            # and gets a freshly-resolved, non-colliding name.
            output_name = self._context.get("output_name") or DEFAULT_NAME

            raw_path = raw_export_path(output_name)
            write_raw_csv(all_records, raw_path)

            occurrences = convert_all(all_records, self._context)
            checklist_rows = build_checklist_rows(occurrences)
            checklist_rows = apply_cleanup(checklist_rows)
            checklist_rows = sort_rows_by_brand(checklist_rows)

            final_path = final_export_path(output_name)
            write_final_csv(checklist_rows, final_path)

            self._on_finished(
                len(new_records), len(all_records), len(checklist_rows), final_path
            )

        except Exception as exc:  # noqa: BLE001
            self._on_error(str(exc))
