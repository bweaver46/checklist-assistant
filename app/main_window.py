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
    QLabel,
)

from scraper.browser_manager import BrowserManager
from exporter.raw_export import write_raw_csv
from exporter.convert import convert_all
from exporter.merge import build_checklist_rows
from exporter.cleanup import apply_cleanup
from exporter.final_export import write_final_csv, sort_rows_by_brand
from settings.window_layout import MAIN_WINDOW_POSITION

# BuySportsCards only sells sports cards, so Type is fixed and never
# asked for. If Checklist Assistant grows to support a non-sports source
# later, this becomes a per-source value instead of a constant.
DEFAULT_TYPE = "Sports"

# Fixed width for the extraction prompts, so long explanatory text wraps
# onto multiple lines instead of stretching the dialog across the screen.
PROMPT_DIALOG_WIDTH = 420


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Checklist Assistant")
        self.resize(480, 240)
        self.move(*MAIN_WINDOW_POSITION)

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

    def _prompt_text(self, title: str, label: str) -> tuple[str, bool]:
        """QInputDialog.getText, but with word-wrap and a fixed width
        so long explanatory text wraps onto multiple lines instead of
        stretching the dialog box across the whole screen."""
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setFixedWidth(PROMPT_DIALOG_WIDTH)

        for child in dialog.findChildren(QLabel):
            child.setWordWrap(True)

        ok = dialog.exec() == QInputDialog.Accepted
        return dialog.textValue(), ok

    def _prompt_for_context(self) -> dict | None:
        """Ask for Sport, Primary Player, Team, and Section once per
        extraction run - the fields that aren't derivable from the row
        data at all. Type is fixed to "Sports" (BSC only sells sports
        cards) and isn't asked for. Primary Player, Team, and Section
        are all optional - leaving them blank is fine, and Section
        should be blank for almost every search. Returns None if the
        user cancels Sport (the one field that really matters).
        """
        sport, ok = self._prompt_text("Extract Checklist", "Sport:")
        if not ok:
            return None

        primary_player, ok = self._prompt_text(
            "Extract Checklist",
            "Primary Player (optional) - if this search is filtered to "
            "one player, type their name here (e.g. Mike Trout). Any "
            "card whose Name field has other text mixed in (insert "
            "titles, other players, acronyms) keeps just this name as "
            "Player and moves the rest into Sub_Type. Leave blank if "
            "not filtered to one player.",
        )
        if not ok:
            primary_player = ""

        team, ok = self._prompt_text(
            "Extract Checklist", "Team (optional, leave blank if not applicable):"
        )
        if not ok:
            team = ""

        section, ok = self._prompt_text(
            "Extract Checklist",
            "Section - leave this BLANK for almost every search. Only "
            "fill it in if this search is specifically a 'continuation' "
            "subsection - one that keeps going where the base set's "
            "numbering left off instead of restarting at 1 (e.g. a "
            "'Prospects' insert numbered #101-200 right after a #1-100 "
            "base set). Type that subsection's name here (e.g. "
            "Prospects) and it'll be recorded correctly without "
            "renumbering anything.",
        )
        if not ok:
            section = ""

        return {
            "sport": sport.strip(),
            "type": DEFAULT_TYPE,
            "primary_player": primary_player.strip(),
            "team": team.strip(),
            "section": section.strip(),
        }

    def on_extract_checklist(self) -> None:
        """Run the full extraction pipeline: ask for Sport/Primary
        Player/Team/Section, read every page, export raw CSV, clean
        each row, group into cards (computing Insert/Sub_Type/Parallels),
        clean up, and export the final CSV.
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

            occurrences = convert_all(records, context)
            checklist_rows = build_checklist_rows(occurrences)
            checklist_rows = apply_cleanup(checklist_rows)
            checklist_rows = sort_rows_by_brand(checklist_rows)

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
