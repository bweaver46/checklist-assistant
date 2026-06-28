"""
Main Window

The desktop UI shell for Checklist Assistant.

Per design philosophy, this window contains almost no scraping logic.
Its job is only to respond to button clicks and delegate to BrowserManager.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QToolBar,
    QStatusBar,
    QInputDialog,
)

from scraper.browser_manager import BrowserManager
from exporter.raw_export import write_raw_csv
from exporter.convert import convert_all
from exporter.merge import merge_parallels
from exporter.cleanup import apply_cleanup
from exporter.final_export import write_final_csv

# BuySportsCards only sells sports cards, so Type is fixed and never
# asked for. If Checklist Assistant grows to support a non-sports source
# later, this becomes a per-source value instead of a constant.
DEFAULT_TYPE = "Sports"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Checklist Assistant")
        self.resize(480, 240)

        self.browser_manager = BrowserManager()

        self._build_toolbar()
        self._build_central_widget()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

    def _build_central_widget(self) -> None:
        central = QWidget()
        layout = QVBoxLayout()

        self.launch_button = QPushButton("Launch Browser")
        self.launch_button.clicked.connect(self.on_launch_browser)
        layout.addWidget(self.launch_button)

        self.extract_button = QPushButton("Extract Checklist")
        self.extract_button.clicked.connect(self.on_extract_checklist)
        layout.addWidget(self.extract_button)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_status_bar(self) -> None:
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def on_launch_browser(self) -> None:
        self.statusBar().showMessage("Launching browser...")
        self.browser_manager.launch()
        url = self.browser_manager.current_url()
        self.statusBar().showMessage(f"Browser ready at {url}")

    def _prompt_for_context(self) -> dict | None:
        """Ask for Sport, Team, and Section once per extraction run -
        the fields that aren't derivable from the row data at all. Type
        is fixed to "Sports" (BSC only sells sports cards) and isn't
        asked for. Team and Section are optional; leaving them blank is
        fine - in fact, leave Section blank unless you're specifically
        extracting a continuation subsection (see below). Returns None
        if the user cancels Sport (the one field that really matters).
        """
        sport, ok = QInputDialog.getText(self, "Extract Checklist", "Sport:")
        if not ok:
            return None

        team, ok = QInputDialog.getText(
            self, "Extract Checklist", "Team (optional, leave blank if not applicable):"
        )
        if not ok:
            team = ""

        section, ok = QInputDialog.getText(
            self,
            "Extract Checklist",
            "Section - leave this BLANK for almost every search.\n\n"
            "Only fill it in if this search is specifically a "
            "'continuation' subsection - one that keeps going where the "
            "base set's numbering left off instead of restarting at 1 "
            "(e.g. a 'Prospects' insert numbered #101-200 right after a "
            "#1-100 base set). Type that subsection's name here "
            "(e.g. Prospects) and it'll be recorded correctly without "
            "renumbering anything.",
        )
        if not ok:
            section = ""

        return {
            "sport": sport.strip(),
            "type": DEFAULT_TYPE,
            "team": team.strip(),
            "section": section.strip(),
        }

    def on_extract_checklist(self) -> None:
        """Run the full extraction pipeline: ask for Sport/Team/Section,
        read every page, export raw CSV, convert to checklist format,
        merge occurrences, clean up, and export the final CSV.
        """
        context = self._prompt_for_context()
        if context is None:
            self.statusBar().showMessage("Extraction cancelled.")
            return

        try:
            self.statusBar().showMessage("Reading rows across all pages...")
            records = self.browser_manager.extract_all_pages()

            print(f"--- Extracted {len(records)} raw rows ---")
            for record in records:
                print(record.to_dict())

            raw_path = os.path.abspath("raw_export.csv")
            write_raw_csv(records, raw_path)

            checklist_rows = convert_all(records, context)
            checklist_rows = merge_parallels(checklist_rows)
            checklist_rows = apply_cleanup(checklist_rows)

            final_path = os.path.abspath("checklist_export.csv")
            write_final_csv(checklist_rows, final_path)

            print(f"Raw CSV written to: {raw_path}")
            print(f"Final CSV written to: {final_path}")

            self.statusBar().showMessage(
                f"Done: {len(records)} rows -> {len(checklist_rows)} cards. "
                f"Saved to {final_path}"
            )
        except RuntimeError as exc:
            self.statusBar().showMessage(str(exc))
