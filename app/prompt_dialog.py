"""
PromptDialog - a single reusable dialog that handles all the extraction
prompts at a consistent fixed width. Replaces QInputDialog and
QMessageBox throughout main_window.py so every box looks the same.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton,
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
