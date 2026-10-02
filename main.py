"""
WZ Resizer — Main Application Entry Point
High-Performance Utilitarian Target-Size Image & Video Compressor.
"""

import sys
import os
import ctypes
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.styles import DARK_THEME_QSS


def load_application_fonts():
    """Loads bundled Ubuntu TTF fonts into QFontDatabase."""
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    if os.path.isdir(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.lower().endswith(".ttf"):
                font_path = os.path.join(fonts_dir, font_file)
                QFontDatabase.addApplicationFont(font_path)


def main():
    # Set Windows App User Model ID so the taskbar groups properly
    if sys.platform == "win32":
        try:
            myappid = "antigravity.wzresizer.app.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # Ensure UTF-8 I/O
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("WZ Resizer")
    app.setOrganizationName("WZ")

    # Load authentic Ubuntu fonts
    load_application_fonts()

    # Configure global Ubuntu font with fallback
    ubuntu_font = QFont("Ubuntu")
    ubuntu_font.setStyleHint(QFont.StyleHint.SansSerif)
    ubuntu_font.setPointSize(10)
    app.setFont(ubuntu_font)

    # Apply Utilitarian Dark Stylesheet
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
