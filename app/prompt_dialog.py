"""
PromptDialog - a single reusable dialog that handles all the extraction
prompts at a consistent fixed width. Replaces QInputDialog and
QMessageBox throughout main_window.py so every box looks the same.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt

DIALOG_WIDTH = 420


class PromptDialog(QDialog):
    """Fixed-width prompt dialog - text input, combo, or yes/no."""

    def __init__(self, parent, title: str, label: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(DIALOG_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(16, 16, 16, 16)

        self._label = QLabel(label)
        self._label.setWordWrap(True)
        self._label.setFixedWidth(DIALOG_WIDTH - 32)
        self._layout.addWidget(self._label)

        self._input: QLineEdit | None = None
        self._combo: QComboBox | None = None
        self.result_text: str = ""
        self.accepted_flag: bool = False

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def text(parent, title: str, label: str, default: str = "") -> tuple[str, bool]:
        d = PromptDialog(parent, title, label)
        d._input = QLineEdit(default)
        d._layout.addWidget(d._input)
        d._add_ok_cancel()
        if d.exec() == QDialog.Accepted:
            return d._input.text(), True
        return default, False

    @staticmethod
    def combo(parent, title: str, label: str,
              items: list[str], default: str = "") -> tuple[str, bool]:
        d = PromptDialog(parent, title, label)
        d._combo = QComboBox()
        d._combo.addItems(items)
        if default in items:
            d._combo.setCurrentIndex(items.index(default))
        d._layout.addWidget(d._combo)
        d._add_ok_cancel()
        if d.exec() == QDialog.Accepted:
            return d._combo.currentText(), True
        return default, False

    @staticmethod
    def question(parent, title: str, label: str,
                 buttons: list[str], default: str) -> str:
        """Returns the label of whichever button was clicked."""
        d = PromptDialog(parent, title, label)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        result_holder: list[str] = [default]

        for name in buttons:
            btn = QPushButton(name)
            btn.setDefault(name == default)
            btn.setAutoDefault(name == default)
            captured = name

            def make_handler(val):
                def handler():
                    result_holder[0] = val
                    d.accept()
                return handler

            btn.clicked.connect(make_handler(captured))
            btn_row.addWidget(btn)

        d._layout.addLayout(btn_row)
        d.exec()
        return result_holder[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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
