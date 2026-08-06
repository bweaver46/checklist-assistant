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
        """Shows one row per FlaggedCard (exporter/team_sanity.py) with a
        checkbox, unchecked by default. Checked = reject (remove from the
        export); unchecked = approve (keep as-is). Returns the set of
        row_index values the user checked to reject. Closing/Cancel is
        treated the same as approving everything - nothing gets removed
        on a dismissed dialog, since silently dropping cards is worse
        than leaving a questionable one in for Brandon to catch by eye
        later."""
        d = PromptDialog(
            parent, title,
            f"{len(flagged)} card(s) flagged for review - team doesn't "
            "look right for this sport. Check any you want REMOVED from "
            "the export; leave unchecked to keep them.",
        )
        d.setFixedWidth(560)

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

        inner.addStretch()
        scroll.setWidget(container)
        d._layout.addWidget(scroll)
        d._add_ok_cancel()
        d.exec()

        return {row_index for cb, row_index in checkboxes if cb.isChecked()}

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
