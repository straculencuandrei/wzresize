"""
Main Window for WZ Resizer desktop application.
Fully responsive, utilitarian, low-latency interface using PyQt6.
English localization throughout the entire application.
"""

import os
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDoubleSpinBox, QComboBox,
    QRadioButton, QButtonGroup, QProgressBar, QSplitter,
    QFileDialog, QLineEdit, QFrame, QMessageBox, QApplication,
    QSlider
)

from ui.drop_area import DropAreaWidget
from ui.log_widget import LogWidget
from core.worker import CompressionWorker
from core.probe import format_size


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WZ Resizer — Target Size Compressor (Images & Videos)")
        self.setMinimumSize(800, 640)
        self.resize(940, 760)

        self.current_file_path: Optional[str] = None
        self.current_meta: Optional[Dict[str, Any]] = None
        self.worker: Optional[CompressionWorker] = None
        self._syncing_size = False

        self._init_ui()
        self._init_shortcuts()
        self._log_welcome()

    def _init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Header Title Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        app_title = QLabel("WZ RESIZER")
        app_title.setObjectName("headerTitle")
        app_subtitle = QLabel("Automated compression and resizing to an exact target file size")
        app_subtitle.setObjectName("fileDetailLabel")

        title_box.addWidget(app_title)
        title_box.addWidget(app_subtitle)
        header.addLayout(title_box)
        header.addStretch()

        badge = QLabel("PyQt6 + FFmpeg + Pillow")
        badge.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600; padding: 4px 8px; border: 1px solid #262930; border-radius: 3px; background-color: transparent;")
        header.addWidget(badge)
        main_layout.addLayout(header)

        # Vertical Splitter: Top controls and Bottom log console
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter, stretch=1)

        # Container for top controls
        controls_container = QWidget()
        controls_container.setObjectName("transparentContainer")
        controls_container.setStyleSheet("background: transparent;")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)

        # 1. Drop Zone Card
        self.drop_area = DropAreaWidget()
        self.drop_area.sig_file_selected.connect(self._on_file_selected)
        controls_layout.addWidget(self.drop_area)

        # 2. Configuration Settings Card
        settings_frame = QFrame()
        settings_frame.setObjectName("card")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(12, 10, 12, 10)
        settings_layout.setSpacing(10)

        # Target Size Row (Numeric input + Unit + Presets)
        target_row = QHBoxLayout()
        target_row.setSpacing(10)

        target_lbl = QLabel("Target Size:")
        target_lbl.setObjectName("sectionTitle")
        target_lbl.setFixedWidth(150)

        self.size_spinbox = QDoubleSpinBox()
        self.size_spinbox.setRange(0.01, 999999.0)
        self.size_spinbox.setDecimals(2)
        self.size_spinbox.setValue(15.0)  # Default 15 MB
        self.size_spinbox.setFixedWidth(110)
        self.size_spinbox.setToolTip("Input precise desired size if slider is not exact enough")
        self.size_spinbox.valueChanged.connect(self._on_spinbox_changed)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["MB", "KB"])
        self.unit_combo.setCurrentText("MB")
        self.unit_combo.setFixedWidth(70)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)

        target_row.addWidget(target_lbl)
        target_row.addWidget(self.size_spinbox)
        target_row.addWidget(self.unit_combo)

        # Quick Preset Buttons
        target_row.addWidget(QLabel("Presets:"))
        presets = [
            ("8 MB", 8.0, "MB"),
            ("15 MB", 15.0, "MB"),
            ("25 MB", 25.0, "MB"),
            ("50 MB", 50.0, "MB"),
            ("100 MB", 100.0, "MB"),
        ]
        for label, val, unit in presets:
            btn = QPushButton(label)
            btn.setObjectName("presetButton")
            btn.clicked.connect(lambda checked, v=val, u=unit: self._apply_preset(v, u))
            target_row.addWidget(btn)

        target_row.addStretch()
        settings_layout.addLayout(target_row)

        # Target Size Slider Row (Max: Original Size down to close to 0)
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        slider_lbl = QLabel("Size Slider:")
        slider_lbl.setObjectName("sectionTitle")
        slider_lbl.setFixedWidth(150)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(100, 102400)  # Initial default 100 KB to 100 MB
        self.size_slider.setValue(15360)       # 15 MB default
        self.size_slider.setToolTip("Adjust target size smoothly from maximum (original size) down towards zero")
        self.size_slider.valueChanged.connect(self._on_slider_changed)

        self.slider_info_label = QLabel("15.00 MB")
        self.slider_info_label.setObjectName("fileDetailValue")
        self.slider_info_label.setFixedWidth(180)

        slider_row.addWidget(slider_lbl)
        slider_row.addWidget(self.size_slider, stretch=1)
        slider_row.addWidget(self.slider_info_label)
        settings_layout.addLayout(slider_row)

        # Compression Mode Row
        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)

        mode_lbl = QLabel("Compression Mode:")
        mode_lbl.setObjectName("sectionTitle")
        mode_lbl.setFixedWidth(150)
        mode_row.addWidget(mode_lbl)

        self.mode_group = QButtonGroup(self)
        self.radio_balanced = QRadioButton("Balanced (downscale + quality)")
        self.radio_balanced.setToolTip("Intelligently scales resolution and bitrate to prevent compression artifacts")
        self.radio_balanced.setChecked(True)

        self.radio_preserve = QRadioButton("Preserve resolution")
        self.radio_preserve.setToolTip("Keeps 100% of original width and height, reducing only quality / bitrate")

        self.radio_scale = QRadioButton("Scale resolution priority")
        self.radio_scale.setToolTip("Prioritizes downscaling resolution to maintain crisp details and high bit density")

        self.mode_group.addButton(self.radio_balanced, 1)
        self.mode_group.addButton(self.radio_preserve, 2)
        self.mode_group.addButton(self.radio_scale, 3)

        mode_row.addWidget(self.radio_balanced)
        mode_row.addWidget(self.radio_preserve)
        mode_row.addWidget(self.radio_scale)
        mode_row.addStretch()
        settings_layout.addLayout(mode_row)

        # Destination Folder Row
        dest_row = QHBoxLayout()
        dest_row.setSpacing(10)

        dest_lbl = QLabel("Export Folder:")
        dest_lbl.setObjectName("sectionTitle")
        dest_lbl.setFixedWidth(150)

        self.dest_default_radio = QRadioButton("Same folder (with _compressed suffix)")
        self.dest_default_radio.setChecked(True)
        self.dest_custom_radio = QRadioButton("Custom folder:")

        self.dest_group = QButtonGroup(self)
        self.dest_group.addButton(self.dest_default_radio)
        self.dest_group.addButton(self.dest_custom_radio)
        self.dest_group.buttonClicked.connect(self._toggle_dest_mode)

        self.dest_path_edit = QLineEdit()
        self.dest_path_edit.setPlaceholderText("Select export destination folder...")
        self.dest_path_edit.setEnabled(False)

        self.browse_dest_btn = QPushButton("Browse...")
        self.browse_dest_btn.setEnabled(False)
        self.browse_dest_btn.clicked.connect(self._choose_custom_dest)

        dest_row.addWidget(dest_lbl)
        dest_row.addWidget(self.dest_default_radio)
        dest_row.addWidget(self.dest_custom_radio)
        dest_row.addWidget(self.dest_path_edit, stretch=1)
        dest_row.addWidget(self.browse_dest_btn)
        settings_layout.addLayout(dest_row)

        controls_layout.addWidget(settings_frame)

        # 3. Action & Progress Area
        action_box = QHBoxLayout()
        action_box.setSpacing(10)

        self.start_btn = QPushButton("Process / Compress")
        self.start_btn.setObjectName("actionButton")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.setMinimumWidth(220)
        self.start_btn.clicked.connect(self.start_compression)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_compression)

        action_box.addWidget(self.start_btn)
        action_box.addWidget(self.cancel_btn)

        # Progress bar and status indicator
        prog_layout = QVBoxLayout()
        prog_layout.setSpacing(2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("Waiting for file selection...")
        self.progress_label.setObjectName("fileDetailLabel")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.progress_label)
        action_box.addLayout(prog_layout, stretch=1)

        controls_layout.addLayout(action_box)

        # Add top controls to splitter
        splitter.addWidget(controls_container)

        # 4. Log Console Area (Bottom of splitter)
        self.log_widget = LogWidget()
        splitter.addWidget(self.log_widget)

        # Initial splitter ratio: ~55% controls, ~45% log
        splitter.setSizes([400, 280])

    def _init_shortcuts(self):
        # Escape key triggers cancel if running
        shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut_esc.activated.connect(self._handle_escape)

    def _handle_escape(self):
        if self.worker and self.worker.isRunning():
            self.cancel_compression()

    def _log_welcome(self):
        self.log_widget.append_log("INFO", "System initialized. Ready for image and video processing.")
        self.log_widget.append_log("INFO", "Drag and drop a file into the area above or click 'Select File...'.")

    def _on_slider_changed(self, value_kb: int):
        if self._syncing_size:
            return
        self._syncing_size = True
        unit = self.unit_combo.currentText().upper()
        if unit == "MB":
            self.size_spinbox.setValue(round(value_kb / 1024.0, 2))
        else:
            self.size_spinbox.setValue(float(value_kb))
        self._update_slider_label()
        self._syncing_size = False

    def _on_spinbox_changed(self, val: float):
        if self._syncing_size:
            return
        self._syncing_size = True
        unit = self.unit_combo.currentText().upper()
        kb_val = int(round(val * 1024)) if unit == "MB" else int(round(val))
        kb_clamped = max(self.size_slider.minimum(), min(self.size_slider.maximum(), kb_val))
        self.size_slider.setValue(kb_clamped)
        self._update_slider_label()
        self._syncing_size = False

    def _on_unit_changed(self, new_unit: str):
        if self._syncing_size:
            return
        self._syncing_size = True
        kb_val = self.size_slider.value()
        if new_unit.upper() == "MB":
            self.size_spinbox.setValue(round(kb_val / 1024.0, 2))
        else:
            self.size_spinbox.setValue(float(kb_val))
        self._update_slider_label()
        self._syncing_size = False

    def _update_slider_label(self):
        kb_val = self.size_slider.value()
        if self.current_meta and "size_bytes" in self.current_meta:
            orig_kb = max(1, int(self.current_meta["size_bytes"] / 1024))
            pct = min(100.0, (kb_val / orig_kb) * 100.0)
            self.slider_info_label.setText(f"{format_size(kb_val * 1024)} ({pct:.1f}% of orig)")
        else:
            self.slider_info_label.setText(f"{format_size(kb_val * 1024)}")

    def _apply_preset(self, val: float, unit: str):
        self._syncing_size = True
        self.unit_combo.setCurrentText(unit)
        self.size_spinbox.setValue(val)
        kb_val = int(val * 1024) if unit == "MB" else int(val)
        kb_clamped = max(self.size_slider.minimum(), min(self.size_slider.maximum(), kb_val))
        self.size_slider.setValue(kb_clamped)
        self._syncing_size = False
        self._update_slider_label()
        self.log_widget.append_log("INFO", f"Preset selected: {val:.1f} {unit}")

    def _toggle_dest_mode(self):
        is_custom = self.dest_custom_radio.isChecked()
        self.dest_path_edit.setEnabled(is_custom)
        self.browse_dest_btn.setEnabled(is_custom)

    def _choose_custom_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if folder:
            self.dest_path_edit.setText(folder)

    def _on_file_selected(self, file_path: str, meta: Dict[str, Any]):
        self.current_file_path = file_path
        self.current_meta = meta
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Ready: {os.path.basename(file_path)}")

        orig_bytes = meta.get("size_bytes", 0)
        orig_kb = max(1, int(orig_bytes / 1024))

        # Dynamically set slider range: from 1 KB up to original file size
        self._syncing_size = True
        self.size_slider.setMinimum(1)
        self.size_slider.setMaximum(orig_kb)

        # Set default target to 50% of original file or current target if already smaller
        curr_target_bytes = self._calculate_target_bytes()
        if curr_target_bytes >= orig_bytes:
            new_kb = max(1, int(orig_kb * 0.5))
            self.size_slider.setValue(new_kb)
            if self.unit_combo.currentText() == "MB":
                self.size_spinbox.setValue(round(new_kb / 1024.0, 2))
            else:
                self.size_spinbox.setValue(float(new_kb))
        else:
            target_kb = max(1, int(curr_target_bytes / 1024))
            self.size_slider.setValue(min(orig_kb, target_kb))

        self._syncing_size = False
        self._update_slider_label()

        f_size = format_size(orig_bytes)
        m_type = meta.get("type", "UNKNOWN").upper()
        self.log_widget.append_log("INFO", f"File loaded: {file_path}")
        self.log_widget.append_log("INFO", f"Type: {m_type} | Current size: {f_size}")

        if m_type == "VIDEO":
            dur = meta.get("duration", 0.0)
            res = f"{meta.get('width', 0)}x{meta.get('height', 0)}"
            fps = meta.get("fps", 0.0)
            self.log_widget.append_log("INFO", f"Video details: Resolution {res}, {fps:.1f} fps, duration {dur:.2f}s")
        elif m_type == "IMAGE":
            res = f"{meta.get('width', 0)}x{meta.get('height', 0)}"
            self.log_widget.append_log("INFO", f"Image details: Resolution {res}, format {meta.get('format', '')}")

    def _calculate_target_bytes(self) -> int:
        val = self.size_spinbox.value()
        unit = self.unit_combo.currentText().upper()
        if unit == "MB":
            return int(val * 1024 * 1024)
        else:
            return int(val * 1024)

    def _get_selected_mode(self) -> str:
        btn_id = self.mode_group.checkedId()
        if btn_id == 2:
            return "preserve_res"
        elif btn_id == 3:
            return "scale_res"
        return "balanced"

    def start_compression(self):
        """Validates inputs and starts asynchronous background worker."""
        if not self.current_file_path or not os.path.isfile(self.current_file_path):
            self.log_widget.append_log("WARN", "No valid file selected for compression!")
            QMessageBox.warning(self, "Attention", "Please select an image or video file first.")
            return

        target_bytes = self._calculate_target_bytes()
        if target_bytes <= 0:
            self.log_widget.append_log("ERROR", "Specified target size is invalid!")
            return

        mode = self._get_selected_mode()
        custom_dir = self.dest_path_edit.text().strip() if self.dest_custom_radio.isChecked() else None

        if custom_dir and not os.path.isdir(custom_dir):
            self.log_widget.append_log("ERROR", f"Specified export folder does not exist: {custom_dir}")
            QMessageBox.critical(self, "Destination Error", "Specified export folder is invalid.")
            return

        # Prepare UI for processing state
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.drop_area.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting processing...")

        # Initialize background worker thread
        self.worker = CompressionWorker(
            input_path=self.current_file_path,
            target_bytes=target_bytes,
            mode=mode,
            custom_output_dir=custom_dir,
            parent=self
        )

        self.worker.sig_log.connect(self.log_widget.append_log)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.sig_error.connect(self._on_worker_error)

        self.worker.start()

    def cancel_compression(self):
        """Cancels running compression."""
        if self.worker and self.worker.isRunning():
            self.log_widget.append_log("WARN", "Sending cancellation signal to active process...")
            self.progress_label.setText("Cancelling in progress...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_worker_progress(self, pct: int, status: str):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(status)

    def _on_worker_finished(self, success: bool, message: str, result: dict):
        self._reset_ui_state()
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText("Completed!")
            if result.get("already_smaller"):
                self.log_widget.append_log("INFO", "File already meets the target size constraint. No copy generated.")
            else:
                out_path = result.get("output_path", "")
                f_size = format_size(result.get("final_size", 0))
                saved_pct = result.get("saved_percentage", 0.0)
                self.log_widget.append_log("SUCCESS", f"Operation completed successfully! Output: {out_path} ({f_size}, -{saved_pct:.1f}%)")

    def _on_worker_error(self, error_message: str, error_code: int):
        self._reset_ui_state()
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Error (code {error_code})")
        self.log_widget.append_log("ERROR", f"Operation failed with code {error_code}: {error_message}")

    def _reset_ui_state(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.drop_area.setEnabled(True)

    def closeEvent(self, event):
        """Ensures worker thread and active FFmpeg processes are cleanly terminated on exit."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Close Confirmation",
                "Compression is currently in progress. Are you sure you want to cancel and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.cancel()
                self.worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
