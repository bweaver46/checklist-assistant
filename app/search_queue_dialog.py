"""
Search Queue dialog - stage multiple searches, test each one against
the live site, and see which ones are safe to actually run later.

Brandon, 2026-08-10: "lets work on staging searches. we need a way to
test each set, and skip searches that fail." Scoped deliberately to
staging + testing only for now - actually running every passed entry
through extraction automatically is the next step after this (see
scraper/search_queue.py's module docstring for the reasoning on why
this is being built up in stages).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QApplication,
)

from app.prompt_dialog import PromptDialog
from scraper.search_queue import StagedSearch, load_queue, save_queue, PASSED, FAILED, UNTESTED
from settings.last_search import load_last_search


class SearchQueueDialog(QDialog):
    def __init__(self, parent, browser_manager) -> None:
        super().__init__(parent)
        self.browser_manager = browser_manager
        self.entries: list[StagedSearch] = load_queue()

        self.setWindowTitle("Search Queue")
        self.setFixedSize(560, 480)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Stage searches here and test each one against the live "
            "site before running it for real. Untested and failed "
            "entries are skipped when the queue actually runs."
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

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._on_close)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for entry in self.entries:
            self.list_widget.addItem(QListWidgetItem(entry.display_line()))

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
        (Brandon, 2026-08-16: "I would like to be able to edit items in
        the que if they havent started running" - nothing here has a
        concept of "started running" yet since Run Queue isn't built,
        so editing is available on every entry for now.)"""
        row = self.list_widget.currentRow()
        if row < 0:
            self.status_label.setText("Select an entry to edit first.")
            return
        entry = self.entries[row]
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
        del self.entries[row]
        save_queue(self.entries)
        self._refresh_list()

    def _on_move_up(self) -> None:
        row = self.list_widget.currentRow()
        if row <= 0:
            self.status_label.setText("Select an entry (not already first) to move up.")
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
        self.entries[row + 1], self.entries[row] = self.entries[row], self.entries[row + 1]
        save_queue(self.entries)
        self._refresh_list()
        self.list_widget.setCurrentRow(row + 1)

    def _run_test(self, entry: StagedSearch) -> None:
        self.status_label.setText(f"Testing: {entry.name}…")
        QApplication.processEvents()
        url = entry.url()
        passed, detail = self.browser_manager.test_search_url(url)
        entry.status = PASSED if passed else FAILED
        entry.status_detail = detail
        save_queue(self.entries)
        self._refresh_list()

    def _on_test_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            self.status_label.setText("Select an entry to test first.")
            return
        self._run_test(self.entries[row])
        self.status_label.setText(f"Done testing {self.entries[row].name}.")

    def _on_test_all(self) -> None:
        for entry in self.entries:
            self._run_test(entry)
        passed_count = sum(1 for e in self.entries if e.status == PASSED)
        failed_count = sum(1 for e in self.entries if e.status == FAILED)
        self.status_label.setText(
            f"Tested {len(self.entries)} search(es) — "
            f"{passed_count} passed, {failed_count} failed."
        )

    def _on_close(self) -> None:
        save_queue(self.entries)
        self.accept()
