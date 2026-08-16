"""
Checklist Assistant entrypoint.

Run with: python main.py
"""

import sys
import traceback

try:
    from PySide6.QtWidgets import QApplication
    from app.main_window import MainWindow

    def main() -> None:
        app = QApplication(sys.argv)
        # On macOS, Qt gives each window's "default" button (the one
        # Enter triggers) a native blue highlight but leaves its text
        # black -- poor contrast (Brandon, 2026-08-16). Targeting just
        # :default here fixes that without touching every other button's
        # normal OS-native look.
        app.setStyleSheet("QPushButton:default { color: white; }")
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    if __name__ == "__main__":
        main()

except BaseException as e:
    if not isinstance(e, SystemExit):
        traceback.print_exc()
        input("Press Enter to close...")
