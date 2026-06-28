"""
Main Window

The desktop UI shell for Checklist Assistant.

Per design philosophy, this window contains almost no scraping logic.
Its job is only to respond to button clicks and delegate to BrowserManager.
"""

from __future__ import annotations

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
        """Ask for Type and Sport once per extraction run - the two
        fields that aren't derivable from the row data at all. Returns
        None if the user cancels either prompt.
        """
        sport, ok = QInputDialog.getText(self, "Extract Checklist", "Sport:")
        if not ok:
            return None

        card_type, ok = QInputDialog.getText(self, "Extract Checklist", "Type:")
        if not ok:
            return None

        return {"sport": sport.strip(), "type": card_type.strip()}

    def on_extract_checklist(self) -> None:
        """Run the full extraction pipeline: ask for Type/Sport, read
        every page, export raw CSV, convert to checklist format, merge
        occurrences, clean up, and export the final CSV.
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

            raw_path = "raw_export.csv"
            write_raw_csv(records, raw_path)

            checklist_rows = convert_all(records, context)
            checklist_rows = merge_parallels(checklist_rows)
            checklist_rows = apply_cleanup(checklist_rows)

            final_path = "checklist_export.csv"
            write_final_csv(checklist_rows, final_path)

            self.statusBar().showMessage(
                f"Done: {len(records)} rows -> {len(checklist_rows)} cards. "
                f"Raw: {raw_path}  Final: {final_path}"
            )
        except RuntimeError as exc:
            self.statusBar().showMessage(str(exc))
