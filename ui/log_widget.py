"""
Dedicated Log Channel / Console widget.
Provides auto-scrolling, color-coded level tags, timestamps,
and clipboard copy / clear operations.
"""

from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QApplication
)


class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Activity Log (Log Channel)")
        title.setObjectName("sectionTitle")

        header_layout.addWidget(title)
        header_layout.addStretch()

        self.copy_btn = QPushButton("Copy log")
        self.copy_btn.setToolTip("Copy entire log to clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)

        self.clear_btn = QPushButton("Clear log")
        self.clear_btn.setToolTip("Clear log console")
        self.clear_btn.clicked.connect(self.clear_logs)

        header_layout.addWidget(self.copy_btn)
        header_layout.addWidget(self.clear_btn)
        layout.addLayout(header_layout)

        # Text Console
        self.console = QTextEdit()
        self.console.setObjectName("logConsole")
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.console, stretch=1)

    def append_log(self, level: str, message: str):
        """Appends a new formatted log line with timestamp and color coding."""
        now_str = datetime.now().strftime("%H:%M:%S")

        # Color mapping for status tags
        colors = {
            "INFO": "#38bdf8",     # Sky blue
            "SUCCESS": "#34d399",  # Mint green
            "WARN": "#fbbf24",     # Amber yellow
            "ERROR": "#f87171",    # Coral red
        }
        tag_color = colors.get(level.upper(), "#94a3b8")

        # Format multiline messages cleanly
        lines = message.replace("\r", "").split("\n")
        first_line = lines[0] if lines else ""

        html = (
            f"<div style='line-height: 1.3;'>"
            f"<span style='color: #64748b;'>[{now_str}]</span> "
            f"<span style='color: {tag_color}; font-weight: 700;'>[{level.upper()}]</span> "
            f"<span style='color: #f1f5f9;'>{self._escape_html(first_line)}</span>"
        )

        for subline in lines[1:]:
            if subline.strip():
                html += f"<br/><span style='color: #94a3b8; padding-left: 20px;'>&nbsp;&nbsp;&nbsp;&nbsp;{self._escape_html(subline)}</span>"

        html += "</div>"

        # Append HTML safely and auto-scroll
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.insertBlock()  # Clean newline separation for plain text copying
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _escape_html(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;")
        )

    def clear_logs(self):
        """Clears the console output."""
        self.console.clear()
        self.append_log("INFO", "Activity log cleared.")

    def copy_to_clipboard(self):
        """Copies plain text content of the console to the clipboard."""
        plain_text = self.console.toPlainText()
        if plain_text:
            QApplication.clipboard().setText(plain_text)
            self.append_log("INFO", "Logs copied to clipboard.")
