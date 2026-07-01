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
    QMessageBox,
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

CHECKLIST_TYPES = ["Set", "Player", "Team"]


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

    def _prompt_combo(self, title: str, label: str, items: list[str]) -> tuple[str, bool]:
        """Drop-down selection dialog with a fixed width."""
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QInputDialog.ComboBoxInput)
        dialog.setComboBoxItems(items)
        dialog.setFixedWidth(PROMPT_DIALOG_WIDTH)

        for child in dialog.findChildren(QLabel):
            child.setWordWrap(True)

        ok = dialog.exec() == QInputDialog.Accepted
        return dialog.textValue(), ok

    def _prompt_fetch_team(self) -> bool:
        """Team isn't shown in the search results table at all - only on
        the 'Add' detail page for each individual card. Fetching it for
        every row is MUCH slower (one extra page visit per card,
        confirmed safe since 'Add' only opens BSC's listing-creation
        form without submitting anything - it doesn't get clicked) and
        should be a deliberate choice, not a silent default."""
        answer = QMessageBox.question(
            self,
            "Extract Checklist",
            "Fetch Team per card from BuySportsCards?\n\n"
            "This is MUCH slower - one extra page visit per card "
            "instead of one per ~50 cards. Worth it for a search that "
            "spans multiple teams (a full set). Not worth it if this "
            "search is all one team/player - choose No and just type "
            "the team once instead.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _prompt_for_context(self) -> dict | None:
        """Ask for checklist type first, then a conditional set of
        questions based on that choice:

        Set:    Sport -> Fetch Team per card? -> (if No) Team -> Section
        Player: Sport -> Primary Player -> Team
        Team:   Sport -> Team

        Returns None if the user cancels on the type or sport prompt.
        """
        # --- Step 1: checklist type ---
        checklist_type, ok = self._prompt_combo(
            "Extract Checklist",
            "What type of checklist are you extracting?",
            CHECKLIST_TYPES,
        )
        if not ok:
            return None

        # --- Step 2: Sport (required for all types) ---
        sport, ok = self._prompt_text("Extract Checklist", "Sport:")
        if not ok:
            return None

        # --- Step 3: type-specific questions ---
        if checklist_type == "Set":
            return self._prompt_set_context(sport)
        elif checklist_type == "Player":
            return self._prompt_player_context(sport)
        else:  # Team
            return self._prompt_team_context(sport)

    def _prompt_set_context(self, sport: str) -> dict | None:
        """Set flow: Fetch Team? -> (if No) Team -> Section."""
        fetch_team = self._prompt_fetch_team()

        team = ""
        if not fetch_team:
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
            "checklist_type": "Set",
            "sport": sport.strip(),
            "type": DEFAULT_TYPE,
            "primary_player": "",
            "team": team.strip(),
            "section": section.strip(),
            "fetch_team": fetch_team,
        }

    def _prompt_player_context(self, sport: str) -> dict | None:
        """Player flow: Primary Player -> Team."""
        primary_player, ok = self._prompt_text(
            "Extract Checklist",
            "Player name (e.g. Mike Trout) - used to extract the "
            "player's name from BSC's Name field. Any card whose Name "
            "field has other text mixed in (insert titles, other "
            "players, acronyms) keeps just this name as Player and "
            "moves the rest into Sub_Type.",
        )
        if not ok:
            primary_player = ""

        team, ok = self._prompt_text(
            "Extract Checklist", "Team (optional, leave blank if not applicable):"
        )
        if not ok:
            team = ""

        return {
            "checklist_type": "Player",
            "sport": sport.strip(),
            "type": DEFAULT_TYPE,
            "primary_player": primary_player.strip(),
            "team": team.strip(),
            "section": "",
            "fetch_team": False,
        }

    def _prompt_team_context(self, sport: str) -> dict | None:
        """Team flow: Team."""
        team, ok = self._prompt_text(
            "Extract Checklist", "Team (optional, leave blank if not applicable):"
        )
        if not ok:
            team = ""

        return {
            "checklist_type": "Team",
            "sport": sport.strip(),
            "type": DEFAULT_TYPE,
            "primary_player": "",
            "team": team.strip(),
            "section": "",
            "fetch_team": False,
        }

    def on_extract_checklist(self) -> None:
        """Run the full extraction pipeline: ask for checklist type and
        its associated context fields, read every page, export raw CSV,
        clean each row, group into cards (computing Insert/Sub_Type/
        Parallels), clean up, and export the final CSV.
        """
        context = self._prompt_for_context()
        if context is None:
            self.statusBar().showMessage("Extraction cancelled.")
            return

        try:
            self.statusBar().showMessage("Reading rows across all pages...")
            records = self.browser_manager.extract_all_pages(fetch_team=context["fetch_team"])

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
