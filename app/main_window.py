"""
Main Window

The desktop UI shell for Checklist Assistant.

Per design philosophy, this window contains almost no scraping logic.
Its job is only to respond to button clicks and delegate to BrowserManager
(for launching) and ExtractionWorker (for the actual extraction pipeline).
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
    QLabel,
    QMessageBox,
    QApplication,
)

from scraper.browser_manager import BrowserManager
from app.extraction_worker import ExtractionWorker
from settings.window_layout import MAIN_WINDOW_POSITION
from settings.last_run import load_last_run, save_last_run
from settings.accumulator import clear_accumulated, accumulated_count

DEFAULT_TYPE = "Sports"
PROMPT_DIALOG_WIDTH = 420
CHECKLIST_TYPES = ["Set", "Player", "Team"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Checklist Assistant")
        self.resize(480, 240)
        self.move(*MAIN_WINDOW_POSITION)

        self.browser_manager = BrowserManager()
        self._worker: ExtractionWorker | None = None

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

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.on_pause_resume)
        self.pause_button.setVisible(False)
        layout.addWidget(self.pause_button)

        self.clear_button = QPushButton("Clear Accumulated Data")
        self.clear_button.clicked.connect(self.on_clear_accumulated)
        layout.addWidget(self.clear_button)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_status_bar(self) -> None:
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------
    # Browser launch
    # ------------------------------------------------------------------

    def on_launch_browser(self) -> None:
        self.statusBar().showMessage("Launching browser...")
        self.browser_manager.launch()
        url = self.browser_manager.current_url()
        self.statusBar().showMessage(f"Browser ready at {url}")

    # ------------------------------------------------------------------
    # Low-level prompt helpers
    # ------------------------------------------------------------------

    def _prompt_text(self, title: str, label: str, default: str = "") -> tuple[str, bool]:
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(default)
        dialog.setFixedWidth(PROMPT_DIALOG_WIDTH)
        for child in dialog.findChildren(QLabel):
            child.setWordWrap(True)
        ok = dialog.exec() == QInputDialog.Accepted
        return dialog.textValue(), ok

    def _prompt_combo(
        self, title: str, label: str, items: list[str], default: str = ""
    ) -> tuple[str, bool]:
        current = items.index(default) if default in items else 0
        value, ok = QInputDialog.getItem(self, title, label, items, current, False)
        return value, ok

    def _prompt_fetch_team(self, last_fetch_team: bool = False) -> bool:
        default_button = QMessageBox.Yes if last_fetch_team else QMessageBox.No
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
            default_button,
        )
        return answer == QMessageBox.Yes

    # ------------------------------------------------------------------
    # "Use same settings?" gate
    # ------------------------------------------------------------------

    def _prompt_reuse_or_new(self, last: dict) -> dict | None:
        checklist_type = last.get("checklist_type", "Set")
        sport = last.get("sport", "")
        team = last.get("team", "")
        primary_player = last.get("primary_player", "")
        section = last.get("section", "")
        fetch_team = last.get("fetch_team", False)

        lines = [f"Type: {checklist_type}", f"Sport: {sport}"]
        if primary_player:
            lines.append(f"Player: {primary_player}")
        if team:
            lines.append(f"Team: {team}")
        if fetch_team:
            lines.append("Fetch Team per card: Yes")
        if section:
            lines.append(f"Section: {section}")

        answer = QMessageBox.question(
            self,
            "Extract Checklist",
            f"Use the same settings as last time?\n\n" + "\n".join(lines),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Cancel:
            return None
        if answer == QMessageBox.Yes:
            return last
        return "ask"  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Full context prompt chains
    # ------------------------------------------------------------------

    def _prompt_for_context(self, defaults: dict | None = None) -> dict | None:
        d = defaults or {}

        checklist_type, ok = self._prompt_combo(
            "Extract Checklist",
            "What type of checklist are you extracting?",
            CHECKLIST_TYPES,
            default=d.get("checklist_type", "Set"),
        )
        if not ok:
            return None

        sport, ok = self._prompt_text(
            "Extract Checklist", "Sport:", default=d.get("sport", "")
        )
        if not ok:
            return None

        if checklist_type == "Set":
            context = self._prompt_set_context(sport, d)
        elif checklist_type == "Player":
            context = self._prompt_player_context(sport, d)
        else:
            context = self._prompt_team_context(sport, d)

        if context is None:
            return None

        return self._prompt_page_range(context, d)

    def _prompt_page_range(self, context: dict, d: dict) -> dict | None:
        """Ask for start and end page. Both default to last-used values.
        Leave end page blank to scrape through to the last page."""
        prior = accumulated_count()
        prior_note = f" ({prior:,} rows already accumulated)" if prior else ""

        start_str, ok = self._prompt_text(
            "Extract Checklist",
            f"Start page (leave blank for page 1){prior_note}:",
            default=str(d.get("start_page", 1)) if d.get("start_page", 1) > 1 else "",
        )
        if not ok:
            return None
        try:
            start_page = max(1, int(start_str.strip())) if start_str.strip() else 1
        except ValueError:
            start_page = 1

        end_str, ok = self._prompt_text(
            "Extract Checklist",
            "End page (leave blank to scrape all remaining pages):",
            default=str(d.get("end_page", "")) if d.get("end_page", 0) else "",
        )
        if not ok:
            return None
        try:
            end_page = max(0, int(end_str.strip())) if end_str.strip() else 0
        except ValueError:
            end_page = 0

        context["start_page"] = start_page
        context["end_page"] = end_page
        return context

    def _prompt_set_context(self, sport: str, d: dict) -> dict | None:
        fetch_team = self._prompt_fetch_team(last_fetch_team=d.get("fetch_team", False))

        team = ""
        if not fetch_team:
            team, ok = self._prompt_text(
                "Extract Checklist",
                "Team (optional, leave blank if not applicable):",
                default=d.get("team", ""),
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
            default=d.get("section", ""),
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

    def _prompt_player_context(self, sport: str, d: dict) -> dict | None:
        primary_player, ok = self._prompt_text(
            "Extract Checklist",
            "Player name (e.g. Mike Trout) - used to extract the "
            "player's name from BSC's Name field. Any card whose Name "
            "field has other text mixed in (insert titles, other "
            "players, acronyms) keeps just this name as Player and "
            "moves the rest into Attributes.",
            default=d.get("primary_player", ""),
        )
        if not ok:
            primary_player = ""

        team, ok = self._prompt_text(
            "Extract Checklist",
            "Team (optional, leave blank if not applicable):",
            default=d.get("team", ""),
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

    def _prompt_team_context(self, sport: str, d: dict) -> dict | None:
        team, ok = self._prompt_text(
            "Extract Checklist",
            "Team (optional, leave blank if not applicable):",
            default=d.get("team", ""),
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

    # ------------------------------------------------------------------
    # Pause / resume
    # ------------------------------------------------------------------

    def on_pause_resume(self) -> None:
        if self._worker is None:
            return
        if self.pause_button.text() == "Pause":
            self._worker.pause()
            # Update label immediately; the "paused" signal will confirm
            # once the worker actually stops.
            self.pause_button.setText("Resume")
            self.statusBar().showMessage("Pausing after current fetch… click Resume when ready.")
        else:
            self._worker.resume()
            self.pause_button.setText("Pause")
            self.statusBar().showMessage("Resuming…")

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_worker_progress(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_worker_paused(self) -> None:
        self.statusBar().showMessage("Paused — click Resume when ready.")

    def _on_worker_resumed(self) -> None:
        self.statusBar().showMessage("Resuming…")

    def _on_worker_finished(self, new_rows: int, total_rows: int, card_count: int, final_path: str) -> None:
        if self._worker is not None:
            context = self._worker._context
            save_last_run(context)
        self._teardown_worker()
        self.statusBar().showMessage(
            f"Done: +{new_rows:,} new rows ({total_rows:,} total accumulated) "
            f"→ {card_count:,} cards. Saved to {final_path}"
        )

    def on_clear_accumulated(self) -> None:
        count = accumulated_count()
        if count == 0:
            self.statusBar().showMessage("No accumulated data to clear.")
            return
        answer = QMessageBox.question(
            self,
            "Clear Accumulated Data",
            f"Clear all {count:,} accumulated rows?\n\n"
            "This removes the data from all previous page-range runs. "
            "The next extraction will start fresh.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            clear_accumulated()
            self.statusBar().showMessage(f"Cleared {count:,} accumulated rows.")

    def _on_worker_error(self, message: str) -> None:
        self._teardown_worker()
        self.statusBar().showMessage(f"Error: {message}")

    def _teardown_worker(self) -> None:
        self._worker = None
        self.extract_button.setEnabled(True)
        self.pause_button.setVisible(False)
        self.pause_button.setText("Pause")

    # ------------------------------------------------------------------
    # Main extraction handler
    # ------------------------------------------------------------------

    def on_extract_checklist(self) -> None:
        last = load_last_run()

        if last is not None:
            result = self._prompt_reuse_or_new(last)
            if result is None:
                self.statusBar().showMessage("Extraction cancelled.")
                return
            elif result == "ask":
                context = self._prompt_for_context(defaults=last)
            else:
                context = result
        else:
            context = self._prompt_for_context()

        if context is None:
            self.statusBar().showMessage("Extraction cancelled.")
            return

        # All dialogs answered - force them off screen before work starts.
        QApplication.processEvents()

        # Disable Extract and show Pause for the duration of the run.
        self.extract_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.pause_button.setVisible(True)

        self._worker = ExtractionWorker(self.browser_manager, context)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.paused.connect(self._on_worker_paused)
        self._worker.resumed.connect(self._on_worker_resumed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
