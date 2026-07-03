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
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    if __name__ == "__main__":
        main()

except BaseException as e:
    if not isinstance(e, SystemExit):
        traceback.print_exc()
        input("Press Enter to close...")
