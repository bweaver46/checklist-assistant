"""
Tests for app/search_queue_dialog.py - specifically Stop (Brandon,
2026-08-16: "When I click the x, it tells me that football is still
running. Let it finish or pause it before closing. It is paused." -
there was no way to actually stop a run once started, even paused).

Qt-level (real PySide6, offscreen platform) since this exercises the
real ExtractionWorker's pause/cancel machinery together with the
dialog, not just pure logic underneath it.
"""

import threading
import time

from PySide6.QtWidgets import QApplication
from unittest.mock import MagicMock, patch

from app.search_queue_dialog import SearchQueueDialog
from scraper.search_queue import StagedSearch, PASSED

_app = QApplication.instance() or QApplication([])


def test_stop_while_paused_resets_entry_to_passed_and_allows_close():
    bm = MagicMock()
    bm.test_search_url.return_value = (True, "5 result(s)")

    dlg = SearchQueueDialog(None, bm)
    entry = StagedSearch(name="Football2024", fields={"keyword": "x"}, status=PASSED)
    dlg.entries = [entry]
    dlg._refresh_list()

    def fake_extract_all_pages(fetch_team, pause_callback, start_page, end_page, on_status, sample_team_by_year):
        dlg._active_worker.pause()

        def click_stop():
            time.sleep(0.05)
            dlg._on_stop()

        threading.Thread(target=click_stop).start()
        pause_callback()  # should raise ExtractionCancelled once Stop lands
        return []  # unreachable if cancellation worked

    bm.extract_all_pages = fake_extract_all_pages

    with patch("app.search_queue_dialog.PromptDialog.question", return_value="Run"):
        dlg._on_run_queue()

    assert entry.status == PASSED
    assert entry.status_detail == "Stopped by user - ready to run again."
    assert dlg.stop_btn.isVisible() is False
    assert dlg.pause_btn.isVisible() is False
    assert dlg._running_entry is None  # closeEvent's guard now passes
