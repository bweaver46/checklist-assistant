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
    QApplication,
)
from app.prompt_dialog import PromptDialog

from scraper.browser_manager import BrowserManager
from scraper.site_detect import detect_source, parse_beckett_url, BSC, BECKETT, TCDB
from scraper.tcdb_pagination import tcdb_page_url
from app.extraction_worker import ExtractionWorker
from settings.window_layout import MAIN_WINDOW_POSITION
from settings.last_run import load_last_run, save_last_run
from settings.accumulator import clear_accumulated, accumulated_count
from settings.team_cache import clear_team_cache
from settings.year_team_cache import clear_year_team_cache
from settings.output_naming import resolve_unique_output_name, final_export_path
from parsers.beckett_parser import parse_beckett_checklist
from parsers.tcdb_parser import parse_tcdb_checklist
from exporter.external_source_mapper import build_checklist_rows as build_external_checklist_rows
from exporter.final_export import write_final_csv, sort_rows_by_brand

DEFAULT_TYPE = "Sports"
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

        self.extract_beckett_button = QPushButton("Extract Beckett Checklist")
        self.extract_beckett_button.clicked.connect(self._extract_beckett)
        layout.addWidget(self.extract_beckett_button)

        self.extract_tcdb_button = QPushButton("Extract TCDB Checklist")
        self.extract_tcdb_button.clicked.connect(self._extract_tcdb)
        layout.addWidget(self.extract_tcdb_button)

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
        site = PromptDialog.question(
            self, "Launch Browser", "Which site?",
            ["BuySportsCards", "Beckett"], "BuySportsCards",
        )

        start_url = (
            "https://www.beckett.com/news" if site == "Beckett"
            else "https://www.buysportscards.com"
        )

        self.statusBar().showMessage(f"Launching browser to {site}...")
        QApplication.processEvents()
        if not self.browser_manager.is_launched:
            self.browser_manager.launch(start_url=start_url)
        else:
            # Already launched - just move the existing browser to the
            # requested site instead of ignoring the choice.
            self.browser_manager.navigate_to_url(start_url)
        self.browser_manager.bring_to_front()
        url = self.browser_manager.current_url()
        self.statusBar().showMessage(f"Browser ready at {url}")

    # ------------------------------------------------------------------
    # Low-level prompt helpers
    # ------------------------------------------------------------------

    def _prompt_text(self, title: str, label: str, default: str = "") -> tuple[str, bool]:
        return PromptDialog.text(self, title, label, default)

    def _prompt_combo(
        self, title: str, label: str, items: list[str], default: str = ""
    ) -> tuple[str, bool]:
        return PromptDialog.combo(self, title, label, items, default)

    def _prompt_fetch_team(self, last_fetch_team: bool = False) -> bool:
        default = "Yes" if last_fetch_team else "No"
        answer = PromptDialog.question(
            self, "Extract Checklist",
            "Fetch Team per card from BuySportsCards?\n\n"
            "For a Set search this is MUCH slower - one extra page "
            "visit per card instead of one per ~50 cards. For a Player "
            "search it's cheap even across a whole career: the first "
            "card of each year gets checked, then it's rechecked every "
            "50 cards - as long as the team keeps matching, the rest of "
            "that year is assumed. Only a year with a real trade gets "
            "checked card-by-card. Choose No only if this player/team "
            "never changed and you'd rather just type the team once.",
            ["Yes", "No"], default,
        )
        return answer == "Yes"

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
        output_name = last.get("output_name", "")

        lines = [f"Type: {checklist_type}", f"Sport: {sport}"]
        if output_name:
            lines.insert(0, f"Export name: {output_name}")
        if primary_player:
            lines.append(f"Player: {primary_player}")
        if team:
            lines.append(f"Team: {team}")
        if fetch_team:
            lines.append("Fetch Team per card: Yes")
        if section:
            lines.append(f"Section: {section}")

        answer = PromptDialog.question(
            self, "Extract Checklist",
            "Use the same settings as last time?\n\n" + "\n".join(lines),
            ["Yes", "No", "Cancel"], "Yes",
        )
        if answer == "Cancel":
            return None
        if answer == "Yes":
            if checklist_type == "Player":
                # Team is the one thing worth re-asking even on reuse -
                # Brandon runs the same player across different team
                # eras/chunks, so silently carrying over last time's
                # team would be wrong more often than it'd help.
                # Pre-filled with the last value so an unchanged team
                # is just hitting OK.
                new_team, ok = self._prompt_text(
                    "Extract Checklist",
                    "Team (optional, leave blank if not applicable):",
                    default=team,
                )
                if ok:
                    last = {**last, "team": new_team.strip()}
                # Player mode no longer offers fetch_team at all - force
                # it off even if an older saved session still has
                # fetch_team: true sitting in last_run.json, or reusing
                # settings would silently re-trigger the auto-fetch
                # machinery this flow no longer asks about.
                last = {**last, "fetch_team": False}
            return last
        return "ask"  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Full context prompt chains
    # ------------------------------------------------------------------

    def _prompt_for_context(self, defaults: dict | None = None) -> dict | None:
        d = defaults or {}

        output_name_raw, ok = self._prompt_text(
            "Extract Checklist",
            "Name this export (e.g. '2026 Topps Chrome Baseball').\n\n"
            "This names the two output files. A new file pair is always "
            "created for this name, so a previous set's export is never "
            "overwritten. Leave blank to use a generic name.\n\n"
            "(If you're continuing THIS SAME set across multiple "
            "page-range runs, answer 'Yes' at the reuse-settings prompt "
            "instead of getting this question again.)",
            default="",
        )
        if not ok:
            return None
        output_name = resolve_unique_output_name(output_name_raw)

        prior = accumulated_count()
        if prior:
            answer = PromptDialog.question(
                self, "Extract Checklist",
                f"{prior:,} rows are already accumulated from a previous "
                "set.\n\n"
                f"If you continue, those rows will be combined into this "
                f"new export ('{output_name}') unless you clear them "
                "first.",
                ["Clear and Continue", "Keep and Continue", "Cancel"],
                "Clear and Continue",
            )
            if answer == "Cancel":
                return None
            if answer == "Clear and Continue":
                clear_accumulated()

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

        context["output_name"] = output_name
        return self._prompt_page_range(context, d)

    def _prompt_page_range(self, context: dict, d: dict) -> dict | None:
        """Ask for start and end page. Both default to last-used values.
        Leave end page blank to scrape through to the last page."""
        prior = accumulated_count()
        prior_note = f" ({prior:,} rows already accumulated)" if prior else ""

        last_start = d.get("start_page", 1)
        start_str, ok = self._prompt_text(
            "Extract Checklist",
            f"Start page (leave blank for page 1){prior_note}:",
            default=str(last_start) if last_start > 1 else "",
        )
        if not ok:
            return None
        try:
            start_page = max(1, int(start_str.strip())) if start_str.strip() else 1
        except ValueError:
            start_page = 1

        # Only pre-fill end page if it was greater than the new start page.
        # A stale end_page <= start_page is always wrong and would stop
        # the run immediately after one page.
        last_end = d.get("end_page", 0)
        end_default = str(last_end) if last_end and last_end > start_page else ""
        end_str, ok = self._prompt_text(
            "Extract Checklist",
            "End page (leave blank to scrape all remaining pages):",
            default=end_default,
        )
        if not ok:
            return None
        try:
            end_page = max(0, int(end_str.strip())) if end_str.strip() else 0
        except ValueError:
            end_page = 0

        # Safety: if end_page ended up <= start_page, treat as no limit.
        if 0 < end_page < start_page:
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

        # Team is always manual for Player mode (fetch_team/year-checkin
        # is no longer offered here per Brandon 2026-07-24 - he has a
        # simpler manual approach; the underlying scraping logic is
        # still in browser_manager.py, just unused by this flow).
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
            self.pause_button.setText("Resume")
            self.statusBar().showMessage("Pausing after current fetch… click Resume when ready.")
        else:
            self._worker.resume()
            self.pause_button.setText("Pause")
            self.statusBar().showMessage("Resuming…")

    # ------------------------------------------------------------------
    # Worker callbacks (called from within the scraping loop)
    # ------------------------------------------------------------------

    def _on_worker_progress(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_worker_paused(self) -> None:
        self.statusBar().showMessage("Paused — click Resume when ready.")

    def _on_worker_resumed(self) -> None:
        self.statusBar().showMessage("Resuming…")

    def _on_worker_finished(self, new_rows: int, total_rows: int, card_count: int, final_path: str) -> None:
        if self._worker is not None:
            save_last_run(self._worker._context)
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
        answer = PromptDialog.question(
            self, "Clear Accumulated Data",
            f"Clear all {count:,} accumulated rows?\n\n"
            "This removes the data from all previous page-range runs. "
            "The next extraction will start fresh.",
            ["Yes", "No"], "No",
        )
        if answer == "Yes":
            clear_accumulated()
            clear_team_cache()
            clear_year_team_cache()
            self.statusBar().showMessage(f"Cleared {count:,} accumulated rows and team cache.")

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
        source = detect_source(self.browser_manager.current_url())

        if source is None:
            self.statusBar().showMessage(
                "Launch the browser and navigate to a BuySportsCards, "
                "Beckett, or TCDB page first."
            )
            return
        if source == BECKETT:
            self._extract_beckett()
            return
        if source == TCDB:
            self._extract_tcdb()
            return
        # source == BSC - existing flow, unchanged.

        last = load_last_run()

        if last is not None:
            result = self._prompt_reuse_or_new(last)
            if result is None:
                self.statusBar().showMessage("Extraction cancelled.")
                return
            elif result == "ask":
                context = self._prompt_for_context(defaults=last)
            else:
                # "Yes" reuses all settings but ALWAYS asks page range -
                # start/end page change every run by definition.
                context = self._prompt_page_range(result, result)
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

        self._worker = ExtractionWorker(
            browser_manager=self.browser_manager,
            context=context,
            on_progress=self._on_worker_progress,
            on_finished=self._on_worker_finished,
            on_error=self._on_worker_error,
            on_paused=self._on_worker_paused,
            on_resumed=self._on_worker_resumed,
        )
        self._worker.run()

    # ------------------------------------------------------------------
    # Beckett extraction (no login, single page - "Full Checklist" tab)
    # ------------------------------------------------------------------

    def _prompt_product_and_sport(
        self, title: str, default_product: str = "", default_sport: str = "",
        debug_url: str | None = None,
    ) -> tuple[str, str] | None:
        """Shared by Beckett/TCDB - neither site gives a clean brand/
        set string separate from the sport the way BSC's own Set
        column does, so Brandon types both once per extraction. These
        get run through the exact same parse_set() logic BSC's rows
        use (year/brand/set split, brand_set_exceptions.csv included).
        default_product/default_sport pre-fill from the URL when it's
        derivable (see scraper.site_detect.parse_beckett_url) - still
        editable, not skipped, in case the guess is wrong.
        debug_url: TEMPORARY - if given, shown in the prompt label so
        we can see exactly what current_url() returned live."""
        label = (
            "Product (e.g. '2025 Bowman', '1972 Topps') - do not "
            "include the sport, that's asked separately:"
        )
        if debug_url is not None:
            label += f"\n\n[debug] current_url() returned: {debug_url!r}"
        product, ok = self._prompt_text(
            title, label, default=default_product,
        )
        if not ok or not product.strip():
            return None

        sport, ok = self._prompt_text(title, "Sport:", default=default_sport)
        if not ok:
            return None

        return product.strip(), sport.strip()

    def _extract_beckett(self) -> None:
        title = "Extract Checklist (Beckett)"

        if not self.browser_manager.is_launched:
            self.statusBar().showMessage(
                "Launch the browser (choose Beckett) and navigate to a "
                "checklist article first."
            )
            return

        # Per Brandon: this used to force-navigate to the news listing
        # page on every single run, which reset wherever he'd already
        # navigated to and was WHY product/sport kept coming up blank
        # (current_url() was reading the reset news-listing URL, not
        # the article). It now just reads wherever the browser already
        # is - same approach _extract_tcdb() already uses - so
        # navigating there once (via Launch Browser -> Beckett, or
        # manually) is all that's needed, and re-running extraction
        # doesn't move the browser out from under you.
        self.browser_manager.bring_to_front()
        current_url = self.browser_manager.current_url() or ""
        derived = parse_beckett_url(current_url)
        default_product, default_sport = derived if derived else ("", "")

        # TEMPORARY DEBUG (remove once the blank-product bug is
        # confirmed fixed): parse_beckett_url() derives correctly for
        # every URL tested in isolation, so this shows the RAW value
        # current_url() actually returned live, to see whether it
        # differs from what the browser's address bar displays.
        answer = self._prompt_product_and_sport(
            title, default_product, default_sport,
            debug_url=current_url,
        )
        if answer is None:
            self.statusBar().showMessage("Extraction cancelled.")
            return
        product, sport = answer

        # Per Brandon: the export name should always just be the
        # product, no separate prompt - it was redundant, and re-typing
        # (or re-confirming) the same thing twice added an extra click
        # for no reason.
        output_name = resolve_unique_output_name(product)

        self.extract_button.setEnabled(False)
        try:
            self.statusBar().showMessage("Clicking Full Checklist tab…")
            QApplication.processEvents()
            try:
                html = self.browser_manager.click_beckett_full_checklist()
                rows = parse_beckett_checklist(html)
            except Exception as exc:  # noqa: BLE001
                self.statusBar().showMessage(f"Error: {exc}")
                return

            if not rows:
                self.statusBar().showMessage(
                    "No cards found on this page - check you're on a "
                    "Beckett checklist article and try again."
                )
                return

            context = {"product": product, "sport": sport}
            checklist_rows = build_external_checklist_rows(rows, context)
            checklist_rows = sort_rows_by_brand(checklist_rows)

            final_path = final_export_path(output_name)
            write_final_csv(checklist_rows, final_path)

            self.statusBar().showMessage(
                f"Done: {len(checklist_rows):,} cards → {final_path}"
            )
        finally:
            self.extract_button.setEnabled(True)

    # ------------------------------------------------------------------
    # TCDB extraction (no login, paginated via ?PageIndex=N)
    # ------------------------------------------------------------------

    def _extract_tcdb(self) -> None:
        title = "Extract Checklist (TCDB)"
        answer = self._prompt_product_and_sport(title)
        if answer is None:
            self.statusBar().showMessage("Extraction cancelled.")
            return
        product, sport = answer

        output_name_raw, ok = self._prompt_text(
            title, "Name this export (e.g. '1972 Topps Baseball'):"
        )
        if not ok:
            self.statusBar().showMessage("Extraction cancelled.")
            return
        output_name = resolve_unique_output_name(output_name_raw)

        start_str, ok = self._prompt_text(
            title, "Start page (leave blank for page 1):"
        )
        if not ok:
            self.statusBar().showMessage("Extraction cancelled.")
            return
        try:
            start_page = max(1, int(start_str.strip())) if start_str.strip() else 1
        except ValueError:
            start_page = 1

        end_str, ok = self._prompt_text(
            title,
            "End page (leave blank to stop as soon as a page comes back empty):",
        )
        if not ok:
            self.statusBar().showMessage("Extraction cancelled.")
            return
        try:
            end_page = max(0, int(end_str.strip())) if end_str.strip() else 0
        except ValueError:
            end_page = 0

        base_url = self.browser_manager.current_url()
        all_rows: list[dict] = []
        page_num = start_page

        self.extract_button.setEnabled(False)
        try:
            while True:
                url = tcdb_page_url(base_url, page_num)
                self.statusBar().showMessage(f"Reading page {page_num}…")
                QApplication.processEvents()
                try:
                    self.browser_manager.navigate_to_url(url)
                    html = self.browser_manager.get_page_html()
                    page_rows = parse_tcdb_checklist(html)
                except Exception as exc:  # noqa: BLE001
                    self.statusBar().showMessage(f"Error on page {page_num}: {exc}")
                    return

                if not page_rows:
                    break

                all_rows.extend(page_rows)
                self.statusBar().showMessage(
                    f"Page {page_num}: {len(page_rows)} rows ({len(all_rows):,} total)"
                )
                QApplication.processEvents()

                if end_page and page_num >= end_page:
                    break
                page_num += 1

            if not all_rows:
                self.statusBar().showMessage(
                    "No cards found - check you're on a TCDB checklist page and try again."
                )
                return

            context = {"product": product, "sport": sport}
            checklist_rows = build_external_checklist_rows(all_rows, context)
            checklist_rows = sort_rows_by_brand(checklist_rows)

            final_path = final_export_path(output_name)
            write_final_csv(checklist_rows, final_path)

            self.statusBar().showMessage(
                f"Done: {len(checklist_rows):,} cards → {final_path}"
            )
        finally:
            self.extract_button.setEnabled(True)
