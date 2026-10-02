"""
Drag-and-Drop and File Selection widget.
Provides interactive visual feedback and displays media specifications upon selection.
"""

import os
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QWidget
)

from core.probe import probe_file, format_size, format_duration


class DropAreaWidget(QFrame):
    sig_file_selected = pyqtSignal(str, dict)  # file_path, metadata dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.current_file: Optional[str] = None
        self.current_meta: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Prompt view (initial state)
        self.prompt_widget = QWidget()
        self.prompt_widget.setObjectName("transparentContainer")
        self.prompt_widget.setStyleSheet("background: transparent;")
        prompt_layout = QVBoxLayout(self.prompt_widget)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(8)
        prompt_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_main = QLabel("Drop file here (Drag & Drop)")
        self.label_main.setObjectName("headerTitle")
        self.label_main.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_sub = QLabel("or choose an image (JPG, PNG, WEBP) or video (MP4, MKV, MOV, WEBM)")
        self.label_sub.setObjectName("fileDetailLabel")
        self.label_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.browse_btn = QPushButton("Select File...")
        self.browse_btn.setFixedWidth(160)
        self.browse_btn.clicked.connect(self._open_file_dialog)

        prompt_layout.addWidget(self.label_main)
        prompt_layout.addWidget(self.label_sub)
        prompt_layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.prompt_widget)

        # File Details view (shown after file is chosen)
        self.details_widget = QWidget()
        self.details_widget.setObjectName("transparentContainer")
        self.details_widget.setStyleSheet("background: transparent;")
        self.details_widget.setVisible(False)
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)

        # Row 1: File name & Change button
        top_row = QHBoxLayout()
        self.file_name_label = QLabel()
        self.file_name_label.setObjectName("headerTitle")
        self.file_name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.change_file_btn = QPushButton("Change File")
        self.change_file_btn.setFixedHeight(26)
        self.change_file_btn.clicked.connect(self._open_file_dialog)

        top_row.addWidget(self.file_name_label)
        top_row.addStretch()
        top_row.addWidget(self.change_file_btn)
        details_layout.addLayout(top_row)

        # Row 2: Specifications summary
        spec_row = QHBoxLayout()
        spec_row.setSpacing(20)

        self.size_val = self._create_spec_item(spec_row, "ORIGINAL SIZE")
        self.type_val = self._create_spec_item(spec_row, "FORMAT & TYPE")
        self.res_val = self._create_spec_item(spec_row, "RESOLUTION")
        self.dur_val = self._create_spec_item(spec_row, "DURATION / FPS")

        spec_row.addStretch()
        details_layout.addLayout(spec_row)
        self.layout.addWidget(self.details_widget)

    def _create_spec_item(self, parent_layout: QHBoxLayout, label_text: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(2)
        lbl = QLabel(label_text)
        lbl.setObjectName("fileDetailLabel")
        val = QLabel("—")
        val.setObjectName("fileDetailValue")
        box.addWidget(lbl)
        box.addWidget(val)
        parent_layout.addLayout(box)
        return val

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragActive", "true")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("dragActive", "false")
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.load_file(file_path)

    def _open_file_dialog(self):
        filters = (
            "All Supported Media (*.jpg *.jpeg *.png *.webp *.mp4 *.mkv *.mov *.webm);;"
            "Images (*.jpg *.jpeg *.png *.webp *.bmp);;"
            "Videos (*.mp4 *.mkv *.mov *.webm *.avi);;"
            "All Files (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose file for compression", "", filters)
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        """Loads and probes a file, updating the visual interface and emitting the signal."""
        try:
            meta = probe_file(file_path)
            self.current_file = file_path
            self.current_meta = meta

            self.file_name_label.setText(os.path.basename(file_path))
            self.file_name_label.setToolTip(file_path)

            self.size_val.setText(format_size(meta["size_bytes"]))

            m_type = meta.get("type", "UNKNOWN").upper()
            m_fmt = meta.get("format", "")
            self.type_val.setText(f"{m_type} ({m_fmt})")

            w, h = meta.get("width", 0), meta.get("height", 0)
            if w > 0 and h > 0:
                self.res_val.setText(f"{w} x {h}")
            else:
                self.res_val.setText("N/A")

            dur = meta.get("duration", 0.0)
            fps = meta.get("fps", 0.0)
            if dur > 0:
                self.dur_val.setText(f"{format_duration(dur)} ({fps:.1f} fps)" if fps > 0 else format_duration(dur))
            elif fps > 0:
                self.dur_val.setText(f"{fps:.1f} fps")
            else:
                self.dur_val.setText("Static")

            self.prompt_widget.setVisible(False)
            self.details_widget.setVisible(True)

            self.sig_file_selected.emit(file_path, meta)

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "File Error", f"Could not analyze file: {e}")

    def clear(self):
        """Resets drop area to empty state."""
        self.current_file = None
        self.current_meta = None
        self.details_widget.setVisible(False)
        self.prompt_widget.setVisible(True)
