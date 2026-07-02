"""
ExtractionWorker

Runs the full extraction pipeline on a background thread so the UI
stays responsive during a long scrape. Supports pause/resume via a
threading.Event that the browser_manager checks between every team
fetch and between every page navigation.
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


class ExtractionWorker(QThread):
    """Background thread for the extraction pipeline.

    Signals
    -------
    progress(str)   Status message to show in the status bar while running.
    finished(int, int, str)
                    Emitted on success: (raw_row_count, card_count, final_csv_path).
    error(str)      Emitted if an exception kills the run.
    paused()        Emitted when the worker actually stops and waits.
    resumed()       Emitted when the worker continues after a pause.
    """

    progress = Signal(str)
    finished = Signal(int, int, str)
    error = Signal(str)
    paused = Signal()
    resumed = Signal()

    def __init__(self, browser_manager: BrowserManager, context: dict) -> None:
        super().__init__()
        self._browser_manager = browser_manager
        self._context = context

        # When the event is SET the worker runs freely.
        # When the event is CLEAR the worker blocks inside _check_pause().
        self._go = threading.Event()
        self._go.set()

    # ------------------------------------------------------------------
    # Pause / resume API  (called from the main thread via button clicks)
    # ------------------------------------------------------------------

    def pause(self) -> None:
        self._go.clear()

    def resume(self) -> None:
        self._go.set()

    def _check_pause(self) -> None:
        """Block here if a pause was requested; emit signals around the
        wait so the main window can update the button label."""
        if not self._go.is_set():
            self.paused.emit()
            self._go.wait()   # blocks until resume() sets the event
            self.resumed.emit()

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            fetch_team = self._context.get("fetch_team", False)

            self.progress.emit("Reading rows across all pages…")
            records = self._browser_manager.extract_all_pages(
                fetch_team=fetch_team,
                pause_callback=self._check_pause,
            )

            self.progress.emit(f"Scraped {len(records)} rows — building checklist…")
            raw_path = os.path.abspath("raw_export.csv")
            write_raw_csv(records, raw_path)

            occurrences = convert_all(records, self._context)
            checklist_rows = build_checklist_rows(occurrences)
            checklist_rows = apply_cleanup(checklist_rows)
            checklist_rows = sort_rows_by_brand(checklist_rows)

            final_path = os.path.abspath("checklist_export.csv")
            write_final_csv(checklist_rows, final_path)

            self.finished.emit(len(records), len(checklist_rows), final_path)

        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
