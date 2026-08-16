"""
PromptDialog - a single reusable dialog that handles all the extraction
prompts at a consistent fixed width. Replaces QInputDialog and
QMessageBox throughout main_window.py so every box looks the same.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTextEdit, QCheckBox, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt

from exporter.team_sanity import load_sport_labels
from settings.last_search import save_last_search

DIALOG_WIDTH = 420


class PromptDialog(QDialog):
    """Fixed-width prompt dialog - text input, combo, or yes/no."""

    def __init__(self, parent, title: str, label: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(DIALOG_WIDTH)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(label)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(DIALOG_WIDTH - 32)
        self._layout.addWidget(lbl)

    def _add_ok_cancel(self) -> None:
        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        self._layout.addLayout(row)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def text(parent, title: str, label: str, default: str = "") -> tuple[str, bool]:
        d = PromptDialog(parent, title, label)
        field = QLineEdit(default)
        d._layout.addWidget(field)
        d._add_ok_cancel()
        ok = d.exec()
        # PySide6 exec() returns int; 1 == Accepted across all versions
        return field.text(), bool(ok)

    @staticmethod
    def combo(parent, title: str, label: str,
              items: list[str], default: str = "") -> tuple[str, bool]:
        d = PromptDialog(parent, title, label)
        box = QComboBox()
        box.addItems(items)
        if default in items:
            box.setCurrentIndex(items.index(default))
        d._layout.addWidget(box)
        d._add_ok_cancel()
        ok = d.exec()
        return box.currentText(), bool(ok)

    @staticmethod
    def error(parent, title: str, message: str) -> None:
        """Show an error with the full text selectable/copyable -
        confirmed 2026-07-26 (Brandon): the status bar shows the full
        message but its text can't be selected/copied, which matters
        for error text he needs to paste elsewhere. Uses a read-only
        QTextEdit rather than QLabel specifically so mouse-drag
        selection and Cmd+C work normally."""
        d = PromptDialog(parent, title, "")
        box = QTextEdit()
        box.setPlainText(message)
        box.setReadOnly(True)
        box.setFixedHeight(120)
        d._layout.addWidget(box)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(d.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(ok)
        d._layout.addLayout(row)
        d.exec()

    @staticmethod
    def review_flags(parent, title: str, flagged: list) -> set[int]:
        """Shows one row per FlaggedCard (exporter/team_sanity.py,
        review_flags() tier only - Boston Braves/New York Giants, the
        genuinely ambiguous cases) with a checkbox, unchecked by
        default. Checked = reject (remove from the export); unchecked =
        approve (keep as-is). Returns the set of row_index values the
        user checked to reject. Closing/Cancel is treated the same as
        approving everything - nothing gets removed on a dismissed
        dialog, since silently dropping cards is worse than leaving a
        questionable one in for Brandon to catch by eye later.

        The clear-cut cross-sport mismatches (certain_flags() tier) never
        reach this dialog at all - those are auto-dropped before this is
        even called (Brandon, 2026-08-06: the first version put all 140+
        of them in here too, which just meant clicking through obviously-
        wrong rows one at a time for no reason)."""
        d = PromptDialog(
            parent, title,
            f"{len(flagged)} card(s) need a judgment call - same team name is "
            "legit in either sport depending on the player/year. Check any you "
            "want REMOVED from the export; leave unchecked to keep them.",
        )
        d.setFixedWidth(560)

        select_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        unselect_all_btn = QPushButton("Unselect All")
        select_row.addWidget(select_all_btn)
        select_row.addWidget(unselect_all_btn)
        select_row.addStretch()
        d._layout.addLayout(select_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(320)
        container = QWidget()
        inner = QVBoxLayout(container)
        checkboxes: list[tuple[QCheckBox, int]] = []

        for card in flagged:
            text = (
                f"#{card.card_number}  {card.player} — {card.team} "
                f"({card.sport}, {card.year})\n{card.reason}"
            )
            cb = QCheckBox(text)
            inner.addWidget(cb)
            checkboxes.append((cb, card.row_index))

        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb, _ in checkboxes])
        unselect_all_btn.clicked.connect(lambda: [cb.setChecked(False) for cb, _ in checkboxes])

        inner.addStretch()
        scroll.setWidget(container)
        d._layout.addWidget(scroll)
        d._add_ok_cancel()
        d.exec()

        return {row_index for cb, row_index in checkboxes if cb.isChecked()}

    @staticmethod
    def build_search_form(parent, defaults: dict[str, str] | None = None) -> dict[str, str] | None:
        """The search-builder form (Brandon, 2026-08-08): Keyword is the
        only required field, matching BSC's own free-text search box -
        everything else narrows it further and is optional. Returns None
        if cancelled or if Keyword was left blank on OK (rather than
        silently building a keyword-less search).

        defaults pre-fills every field (Brandon, 2026-08-16: "when adding
        a search it should maintain all of the fields from the last time
        it was filled out so that if only one field changes I don't have
        to fill it out again"). Callers building a NEW search pass
        load_last_search()'s result; callers EDITING an existing staged
        entry pass that entry's own fields instead - see
        SearchQueueDialog._on_edit. Sport is a QComboBox (2026-08-16:
        "I think sport should be a dropdown list"), populated from
        settings/sport_teams.csv via load_sport_labels - editable so an
        as-yet-unlisted sport can still be typed in, same growable spirit
        as sport_teams.csv itself."""
        d = PromptDialog(
            parent, "Build a Search",
            "Keyword is required (this is BSC's own search box - one or "
            "more words). Everything else narrows the search further and "
            "can be left blank.",
        )
        d.setFixedWidth(460)
        defaults = defaults or {}

        fields: dict[str, QLineEdit | QComboBox] = {}
        FORM_FIELDS = [
            ("keyword", "Keyword (required)"),
            ("sport", "Sport"),
            ("year", "Year"),
            ("set", "Set"),
            ("variant", "Variant (Base / Insert / Parallel)"),
            ("variant_name", "Variant Name"),
            ("attribute", "Card Attribute"),
            ("player", "Player"),
            ("team", "Team"),
            ("card_number", "Card Number"),
        ]
        for key, label_text in FORM_FIELDS:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(220)
            if key == "sport":
                field = QComboBox()
                field.setEditable(True)
                field.addItems(load_sport_labels())
                default_value = defaults.get("sport", "")
                if default_value:
                    idx = field.findText(default_value)
                    if idx >= 0:
                        field.setCurrentIndex(idx)
                    else:
                        field.setCurrentText(default_value)
            else:
                field = QLineEdit()
                field.setText(defaults.get(key, ""))
            row.addWidget(lbl)
            row.addWidget(field)
            d._layout.addLayout(row)
            fields[key] = field

        d._add_ok_cancel()
        ok = d.exec()
        if not ok:
            return None

        values = {
            key: (field.currentText() if isinstance(field, QComboBox) else field.text()).strip()
            for key, field in fields.items()
        }
        if not values["keyword"]:
            return None
        save_last_search(values)
        return values

    @staticmethod
    def question(parent, title: str, label: str,
                 buttons: list[str], default: str) -> str:
        """Returns the label of whichever button was clicked."""
        d = PromptDialog(parent, title, label)
        result_holder: list[str] = [default]

        row = QHBoxLayout()
        row.addStretch()
        for name in buttons:
            btn = QPushButton(name)
            btn.setDefault(name == default)
            btn.setAutoDefault(name == default)

            def make_handler(val: str):
                def handler():
                    result_holder[0] = val
                    d.accept()
                return handler

            btn.clicked.connect(make_handler(name))
            row.addWidget(btn)

        d._layout.addLayout(row)
        d.exec()
        return result_holder[0]
