"""
ExtractionWorker

Runs the full extraction pipeline on a background thread so the UI
stays responsive during a long scrape. Supports pause/resume via a
threading.Event that the browser_manager checks between every team
fetch and between every page navigation.

Accumulation: raw rows from each run are appended to
settings/accumulator.json so the final CSV always reflects everything
scraped so far across all page-range batches. Clear Accumulated Data
resets that file.
"""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import QThread, Signal

from scraper.browser_manager import BrowserManager
from exporter.raw_export import write_raw_csv
from exporter.convert import convert_all
from exporter.merge import build_checklist_rows
from exporter.cleanup import apply_cleanup
from exporter.final_export import write_final_csv, sort_rows_by_brand
from settings.accumulator import load_accumulated, save_accumulated
from settings.team_cache import load_team_cache, save_team_cache


class ExtractionWorker(QThread):
    """Background thread for the extraction pipeline.

    Signals
    -------
    progress(str)
        Status message to show in the status bar while running.
    finished(int, int, int, str)
        On success: (new_rows, total_rows, card_count, final_csv_path).
    error(str)
        Emitted if an exception kills the run.
    paused()
        Emitted when the worker actually stops and waits.
    resumed()
        Emitted when the worker continues after a pause.
    """

    progress = Signal(str)
    finished = Signal(int, int, int, str)
    error = Signal(str)
    paused = Signal()
    resumed = Signal()

    def __init__(self, browser_manager: BrowserManager, context: dict) -> None:
        super().__init__()
        self._browser_manager = browser_manager
        self._context = context

        # When the event is SET the worker runs freely.
        # When CLEAR it blocks inside _check_pause().
        self._go = threading.Event()
        self._go.set()

    # ------------------------------------------------------------------
    # Pause / resume API (called from the main thread)
    # ------------------------------------------------------------------

    def pause(self) -> None:
        self._go.clear()

    def resume(self) -> None:
        self._go.set()

    def _check_pause(self) -> None:
        if not self._go.is_set():
            self.paused.emit()
            self._go.wait()
            self.resumed.emit()

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            fetch_team = self._context.get("fetch_team", False)
            start_page = self._context.get("start_page", 1)
            end_page = self._context.get("end_page", 0)

            # Load the persisted team cache so players seen in previous
            # runs don't need their "Add" page visited again.
            if fetch_team:
                self._browser_manager._team_cache = load_team_cache()
                cached_count = len(self._browser_manager._team_cache)
                if cached_count:
                    self.progress.emit(
                        f"Loaded {cached_count:,} cached team lookups from previous runs…"
                    )

            page_desc = f"pages {start_page}–{end_page}" if end_page else f"page {start_page} onwards"
            self.progress.emit(f"Scraping {page_desc}…")

            new_records = self._browser_manager.extract_all_pages(
                fetch_team=fetch_team,
                pause_callback=self._check_pause,
                start_page=start_page,
                end_page=end_page,
            )

            # Save the team cache back so the next run picks up where
            # this one left off without re-fetching any player.
            if fetch_team:
                save_team_cache(self._browser_manager._team_cache)

            # Load whatever was accumulated from previous runs and
            # append this batch so the CSV reflects all runs combined.
            prior_records = load_accumulated()
            all_records = prior_records + new_records
            save_accumulated(all_records)

            self.progress.emit(
                f"Scraped {len(new_records)} new rows "
                f"({len(prior_records)} prior + {len(new_records)} this run "
                f"= {len(all_records)} total) — building checklist…"
            )

            raw_path = os.path.abspath("raw_export.csv")
            write_raw_csv(all_records, raw_path)

            occurrences = convert_all(all_records, self._context)
            checklist_rows = build_checklist_rows(occurrences)
            checklist_rows = apply_cleanup(checklist_rows)
            checklist_rows = sort_rows_by_brand(checklist_rows)

            final_path = os.path.abspath("checklist_export.csv")
            write_final_csv(checklist_rows, final_path)

            self.finished.emit(
                len(new_records), len(all_records), len(checklist_rows), final_path
            )

        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
