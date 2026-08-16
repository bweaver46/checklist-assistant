"""
Search Queue dialog - stage multiple searches, test each one against
the live site, then run every passed entry through real extraction,
one output file per search (Run Queue).

Brandon, 2026-08-10: "lets work on staging searches. we need a way to
test each set, and skip searches that fail." Staging + per-entry
testing shipped first; Run Queue itself was specced out and built
2026-08-16 per this back-and-forth:
- Manual trigger: review the queue, hit one button to kick off every
  approved (passed) search in order.
- Reorder, add, and edit not-yet-started entries freely - including
  WHILE a run is in progress - since none of that touches the entry
  actually being processed right now. Only the currently-running entry
  itself is locked.
- Pause stops the in-progress extraction wherever it is (reuses
  ExtractionWorker's existing per-page pause/resume, the same
  mechanism the main window's Pause button already uses).
- Each search gets its own output file, named "[year] [set] [sport]"
  from that search's own fields.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QApplication,
)

from app.prompt_dialog import PromptDialog
from app.extraction_worker import ExtractionWorker
from scraper.search_queue import (
    StagedSearch, load_queue, save_queue,
    UNTESTED, PASSED, FAILED, RUNNING, DONE, ERROR,
)
from settings.last_search import load_last_search
from settings.output_naming import resolve_unique_output_name
from settings.accumulator import clear_accumulated

# Matches main_window.DEFAULT_TYPE - duplicated here (not imported) to
# avoid a circular import, since main_window.py itself imports this
# dialog. Same stable literal ("Sports") either way.
DEFAULT_TYPE = "Sports"


class SearchQueueDialog(QDialog):
    def __init__(self, parent, browser_manager) -> None:
        super().__init__(parent)
        self.browser_manager = browser_manager
        self.entries: list[StagedSearch] = load_queue()
        self._running_entry: StagedSearch | None = None
        self._active_worker: ExtractionWorker | None = None
        self._queue_running = False

        self.setWindowTitle("Search Queue")
        self.setFixedSize(560, 520)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Stage searches here and test each one against the live "
            "site before running it for real. Untested and failed "
            "entries are skipped when Run Queue runs. Add, edit, and "
            "reorder freely at any time - only the entry currently "
            "running is locked."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._refresh_list()

        entry_row = QHBoxLayout()
        add_btn = QPushButton("Add Search")
        add_btn.clicked.connect(self._on_add)
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._on_edit)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove)
        entry_row.addWidget(add_btn)
        entry_row.addWidget(edit_btn)
        entry_row.addWidget(remove_btn)
        layout.addLayout(entry_row)

        reorder_row = QHBoxLayout()
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self._on_move_up)
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self._on_move_down)
        reorder_row.addWidget(move_up_btn)
        reorder_row.addWidget(move_down_btn)
        layout.addLayout(reorder_row)

        test_row = QHBoxLayout()
        test_selected_btn = QPushButton("Test Selected")
        test_selected_btn.clicked.connect(self._on_test_selected)
        test_all_btn = QPushButton("Test All")
        test_all_btn.clicked.connect(self._on_test_all)
        test_row.addWidget(test_selected_btn)
        test_row.addWidget(test_all_btn)
        layout.addLayout(test_row)
        self.test_selected_btn = test_selected_btn
        self.test_all_btn = test_all_btn

        run_row = QHBoxLayout()
        self.run_queue_btn = QPushButton("Run Queue")
        self.run_queue_btn.clicked.connect(self._on_run_queue)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._on_pause_resume)
        self.pause_btn.setVisible(False)
        run_row.addWidget(self.run_queue_btn)
        run_row.addWidget(self.pause_btn)
        layout.addLayout(run_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self._on_close)
        close_row.addWidget(self.close_btn)
        layout.addLayout(close_row)

    def _refresh_list(self) -> None:
        selected = self.list_widget.currentRow()
        self.list_widget.clear()
        for entry in self.entries:
            self.list_widget.addItem(QListWidgetItem(entry.display_line()))
        if 0 <= selected < len(self.entries):
            self.list_widget.setCurrentRow(selected)

    def _locked(self, entry: StagedSearch) -> bool:
        """True if entry is the one currently running - every other
        entry stays editable/reorderable/removable during a run."""
        return entry is self._running_entry

    def _on_add(self) -> None:
        fields = PromptDialog.build_search_form(self, defaults=load_last_search())
        if fields is None:
            return
        name, ok = PromptDialog.text(
            self, "Name This Search",
            "Short name for this staged search (shown in the queue list):",
            default=fields.get("keyword", ""),
        )
        if not ok or not name.strip():
            return
        self.entries.append(StagedSearch(name=name.strip(), fields=fields))
        save_queue(self.entries)
        self._refresh_list()

    def _on_edit(self) -> None:
        """Re-opens the search form pre-filled with THIS entry's own
        fields (not the global last-used ones) so Brandon can tweak just
        what changed. Resets status to untested since a field change can
        invalidate a prior pass/fail result - re-test before running.
        Refused only if this specific entry is the one currently
        running (Brandon, 2026-08-16: "I would like to be able to edit
        items in the que if they havent started running")."""
        row = self.list_widget.currentRow()
        if row < 0:
            self.status_label.setText("Select an entry to edit first.")
            return
        entry = self.entries[row]
        if self._locked(entry):
            self.status_label.setText(f"{entry.name} is currently running - wait for it to finish.")
            return
        fields = PromptDialog.build_search_form(self, defaults=entry.fields)
        if fields is None:
            return
        entry.fields = fields
        entry.status = UNTESTED
        entry.status_detail = ""
        save_queue(self.entries)
        self._refresh_list()
        self.status_label.setText(f"Updated {entry.name} — re-test before running.")

    def _on_remove(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            self.status_label.setText("Select an entry to remove first.")
            return
        entry = self.entries[row]
        if self._locked(entry):
            self.status_label.setText(f"{entry.name} is currently running - wait for it to finish.")
            return
        del self.entries[row]
        save_queue(self.entries)
        self._refresh_list()

    def _on_move_up(self) -> None:
        row = self.list_widget.currentRow()
        if row <= 0:
            self.status_label.setText("Select an entry (not already first) to move up.")
            return
        if self._locked(self.entries[row]) or self._locked(self.entries[row - 1]):
            self.status_label.setText("Can't reorder past the entry currently running.")
            return
        self.entries[row - 1], self.entries[row] = self.entries[row], self.entries[row - 1]
        save_queue(self.entries)
        self._refresh_list()
        self.list_widget.setCurrentRow(row - 1)

    def _on_move_down(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.entries) - 1:
            self.status_label.setText("Select an entry (not already last) to move down.")
            return
        if self._locked(self.entries[row]) or self._locked(self.entries[row + 1]):
            self.status_label.setText("Can't reorder past the entry currently running.")
            return
        self.entries[row + 1], self.entries[row] = self.entries[row], self.entries[row + 1]
        save_queue(self.entries)
        self._refresh_list()
        self.list_widget.setCurrentRow(row + 1)

    def _run_test(self, entry: StagedSearch) -> None:
        if self._locked(entry):
            return
        self.status_label.setText(f"Testing: {entry.name}…")
        QApplication.processEvents()
        url = entry.url()
        passed, detail = self.browser_manager.test_search_url(url)
        entry.status = PASSED if passed else FAILED
        entry.status_detail = detail
        save_queue(self.entries)
        self._refresh_list()

    def _on_test_selected(self) -> None:
        if self._queue_running:
            self.status_label.setText(
                "Can't test while Run Queue is going — Test and the "
                "running extraction share the same browser page, "
                "testing something else would navigate it away mid-scrape."
            )
            return
        row = self.list_widget.currentRow()
        if row < 0:
            self.status_label.setText("Select an entry to test first.")
            return
        if self._locked(self.entries[row]):
            self.status_label.setText(f"{self.entries[row].name} is currently running.")
            return
        self._run_test(self.entries[row])
        self.status_label.setText(f"Done testing {self.entries[row].name}.")

    def _on_test_all(self) -> None:
        if self._queue_running:
            self.status_label.setText(
                "Can't test while Run Queue is going — Test and the "
                "running extraction share the same browser page, "
                "testing something else would navigate it away mid-scrape."
            )
            return
        for entry in self.entries:
            self._run_test(entry)
        passed_count = sum(1 for e in self.entries if e.status == PASSED)
        failed_count = sum(1 for e in self.entries if e.status == FAILED)
        self.status_label.setText(
            f"Tested {len(self.entries)} search(es) — "
            f"{passed_count} passed, {failed_count} failed."
        )

    # ------------------------------------------------------------------
    # Run Queue
    # ------------------------------------------------------------------

    def _on_run_queue(self) -> None:
        pending = [e for e in self.entries if e.status == PASSED]
        if not pending:
            self.status_label.setText("No passed entries to run - test some searches first.")
            return

        answer = PromptDialog.question(
            self, "Run Queue",
            f"Run {len(pending)} passed search(es) now?\n\n"
            "Each produces its own output file named "
            "\"[year] [set] [sport]\" from that search's fields. "
            "You can still add, edit, and reorder anything that "
            "hasn't started yet while this runs - but not Test, since "
            "testing shares the same browser page as the running "
            "extraction.",
            ["Run", "Cancel"], "Run",
        )
        if answer != "Run":
            return

        # Locked for the duration of the whole queue run, not just one
        # item - re-entrant runs and a mid-run Close would both leave
        # things in an inconsistent state (see closeEvent below). Test
        # is locked too (not just the running entry, see _locked) since
        # it drives the SAME shared browser page the running extraction
        # is actively reading from - testing something else would
        # navigate that page away mid-scrape (found live, 2026-08-16).
        self.run_queue_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.test_selected_btn.setEnabled(False)
        self.test_all_btn.setEnabled(False)
        self._queue_running = True

        ran = 0
        # Re-reads self.entries for the next PASSED one on every
        # iteration (rather than snapshotting `pending` once) so a
        # search added or edited-then-repassed WHILE the queue is
        # running gets picked up, matching "add more to it... and
        # continue" from the spec.
        while True:
            next_entry = next((e for e in self.entries if e.status == PASSED), None)
            if next_entry is None:
                break
            self._run_one(next_entry)
            ran += 1

        self._queue_running = False
        self.run_queue_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.test_selected_btn.setEnabled(True)
        self.test_all_btn.setEnabled(True)
        self.status_label.setText(f"Queue run finished — {ran} search(es) processed.")

    def _run_one(self, entry: StagedSearch) -> None:
        self._running_entry = entry
        entry.status = RUNNING
        entry.status_detail = "Running…"
        save_queue(self.entries)
        self._refresh_list()
        self.status_label.setText(f"Running: {entry.name}…")
        QApplication.processEvents()

        # One output file per search (Brandon, 2026-08-16) - clear
        # accumulated rows first so this search's data doesn't merge
        # into a previous item's file the way a manual multi-page
        # continuation intentionally would.
        clear_accumulated()

        # Bug found live, 2026-08-16 (Brandon: "everything passes teh
        # test but when I run it just creates blank files"): a plain
        # navigate_to_url() here, immediately followed by extraction,
        # raced BSC's client-side rendering - read_all_rows' count()
        # doesn't auto-wait for elements to appear the way Playwright's
        # action methods do, so it was reading 0 rows every time before
        # the results had actually rendered. The MANUAL flow never hit
        # this because clicking through several prompts (output name,
        # checklist type, sport, team, section, page range) before
        # extraction starts happens to give the page time to finish
        # loading - nothing was ever explicitly waiting for it. Reusing
        # test_search_url() here (same one Test Selected/Test All already
        # use) gets that explicit wait for free, and its own count is a
        # live re-check right before extraction, not just a rerun of
        # whatever passed earlier - if the site genuinely has nothing
        # right now, this fails loudly as an error instead of quietly
        # writing an empty file.
        url = entry.url()
        passed, detail = self.browser_manager.test_search_url(url)
        if not passed:
            self._running_entry = None
            entry.status = ERROR
            entry.status_detail = f"Re-check before running failed: {detail}"
            save_queue(self.entries)
            self._refresh_list()
            return
        self.browser_manager.bring_to_front()

        output_name = resolve_unique_output_name(entry.output_name())
        context = {
            "checklist_type": "Set",
            "sport": entry.fields.get("sport", "").strip(),
            "type": DEFAULT_TYPE,
            "primary_player": "",
            "team": entry.fields.get("team", "").strip(),
            "section": "",
            # Same choice as pulling a Set manually (Brandon, 2026-08-16:
            # "It needs to have the same logic as when I pull a set...
            # that team is applied to every card, we are not opening
            # them to look for the team" for the unchecked case). Set on
            # the search itself via the Pull Team checkbox in
            # PromptDialog.build_search_form - "true" fetches Team from
            # each card's detail page (slow), anything else means the
            # "team" value above is a blanket value with no per-card
            # lookup at all.
            "fetch_team": entry.fields.get("fetch_team", "false") == "true",
            "start_page": 1,
            "end_page": 0,
            "output_name": output_name,
        }

        result: dict = {}

        def on_finished(new_rows, total_rows, card_count, final_path):
            result["ok"] = True
            result["detail"] = f"{card_count:,} cards → {final_path}"

        def on_error(message):
            result["ok"] = False
            result["detail"] = message

        def on_progress(message):
            self.status_label.setText(f"{entry.name}: {message}")
            QApplication.processEvents()

        def on_paused():
            self.status_label.setText(f"{entry.name}: paused — click Resume when ready.")

        def on_resumed():
            self.status_label.setText(f"{entry.name}: resuming…")

        def on_review_flags(flagged):
            return PromptDialog.review_flags(self, "Review Flagged Cards", flagged)

        worker = ExtractionWorker(
            browser_manager=self.browser_manager,
            context=context,
            on_progress=on_progress,
            on_finished=on_finished,
            on_error=on_error,
            on_paused=on_paused,
            on_resumed=on_resumed,
            on_review_flags=on_review_flags,
        )
        self._active_worker = worker
        self.pause_btn.setVisible(True)
        self.pause_btn.setText("Pause")

        worker.run()  # blocks (pumping Qt events internally) until this item finishes, errors, or is paused/resumed through to completion

        self._active_worker = None
        self.pause_btn.setVisible(False)
        self._running_entry = None

        if result.get("ok"):
            entry.status = DONE
            entry.status_detail = result.get("detail", "Done.")
        else:
            entry.status = ERROR
            entry.status_detail = result.get("detail", "Failed.")
        save_queue(self.entries)
        self._refresh_list()

    def _on_pause_resume(self) -> None:
        if self._active_worker is None:
            return
        if self.pause_btn.text() == "Pause":
            self._active_worker.pause()
            self.pause_btn.setText("Resume")
        else:
            self._active_worker.resume()
            self.pause_btn.setText("Pause")

    def closeEvent(self, event) -> None:
        if self._running_entry is not None:
            event.ignore()
            self.status_label.setText(
                f"{self._running_entry.name} is still running - "
                "let it finish (or Pause it) before closing."
            )
            return
        save_queue(self.entries)
        event.accept()

    def _on_close(self) -> None:
        if self._running_entry is not None:
            self.status_label.setText(
                f"{self._running_entry.name} is still running - "
                "let it finish (or Pause it) before closing."
            )
            return
        save_queue(self.entries)
        self.accept()
