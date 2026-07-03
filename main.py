"""
Checklist Assistant entrypoint.

Run with: python main.py
"""

import sys
import traceback

print("Starting Checklist Assistant...")

try:
    print("Importing PySide6...")
    from PySide6.QtWidgets import QApplication
    print("Importing MainWindow...")
    from app.main_window import MainWindow
    print("Imports OK - launching window...")

    def main() -> None:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        print("Window shown - entering event loop...")
        ret = app.exec()
        print(f"Event loop exited with code {ret}")
        sys.exit(ret)

    if __name__ == "__main__":
        main()

except BaseException as e:
    print(f"\nCRASH: {type(e).__name__}: {e}")
    traceback.print_exc()
    input("Press Enter to close...")
