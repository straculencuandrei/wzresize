"""
Utilitarian, clean, high-performance dark theme stylesheet for WZ Resizer.
Strictly focused on clarity, low latency, and zero graphical fluff.
"""

DARK_THEME_QSS = """
/* Global Application Reset */
* {
    font-family: 'Ubuntu', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* Root Window and Central Container */
QMainWindow, QDialog, QWidget#centralWidget {
    background-color: #121316;
}

/* All labels and text items are completely transparent to avoid black square artifacts */
QLabel {
    background-color: transparent;
    border: none;
}

/* Main Cards and Panels */
QFrame#card {
    background-color: #1a1b20;
    border: 1px solid #2d3139;
    border-radius: 4px;
    padding: 10px;
}

/* Headings and Titles */
QLabel#headerTitle {
    background-color: transparent;
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: 0.5px;
}

QLabel#sectionTitle {
    background-color: transparent;
    font-size: 12px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QLabel#fileDetailLabel {
    background-color: transparent;
    font-size: 12px;
    color: #94a3b8;
}

QLabel#fileDetailValue {
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
    color: #f1f5f9;
}

/* Drag and Drop Zone */
QFrame#dropZone {
    background-color: #16181d;
    border: 2px dashed #374151;
    border-radius: 6px;
    min-height: 110px;
}

QFrame#dropZone:hover {
    background-color: #1c2027;
    border-color: #0284c7;
}

QFrame#dropZone[dragActive="true"] {
    background-color: #17253b;
    border-color: #38bdf8;
}

/* Ensure inner widgets inside drop zone and cards are transparent */
QFrame#dropZone QWidget,
QFrame#card QWidget {
    background-color: transparent;
}

/* Input Fields & Spinboxes */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #1e2128;
    border: 1px solid #374151;
    border-radius: 3px;
    padding: 6px 10px;
    color: #f8fafc;
    font-size: 13px;
    min-height: 20px;
}

QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0284c7;
    background-color: #242832;
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #2a2e38;
    border-left: 1px solid #374151;
    width: 20px;
}

QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #3b4252;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #cbd5e1;
    width: 0;
    height: 0;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #cbd5e1;
    width: 0;
    height: 0;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #374151;
    background-color: #262a34;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94a3b8;
    width: 0;
    height: 0;
}

QComboBox QAbstractItemView {
    background-color: #1a1c22;
    border: 1px solid #374151;
    selection-background-color: #0284c7;
    color: #e2e8f0;
    outline: none;
}

/* Radio Buttons */
QRadioButton {
    background-color: transparent;
    spacing: 8px;
    color: #cbd5e1;
    font-size: 13px;
}

QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border-radius: 7px;
    border: 1px solid #475569;
    background-color: #1a1c22;
}

QRadioButton::indicator:hover {
    border-color: #0284c7;
}

QRadioButton::indicator:checked {
    border-color: #38bdf8;
    background-color: #0284c7;
}

/* General Buttons */
QPushButton {
    background-color: #242831;
    border: 1px solid #374151;
    border-radius: 3px;
    padding: 7px 14px;
    color: #f1f5f9;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #2e3440;
    border-color: #4b5563;
}

QPushButton:pressed {
    background-color: #1b1e25;
}

QPushButton:disabled {
    background-color: #16181d;
    border-color: #262a33;
    color: #4b5563;
}

/* Primary Action Button */
QPushButton#actionButton {
    background-color: #0284c7;
    border: 1px solid #0369a1;
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 4px;
}

QPushButton#actionButton:hover {
    background-color: #0369a1;
    border-color: #075985;
}

QPushButton#actionButton:pressed {
    background-color: #0c4a6e;
}

QPushButton#actionButton:disabled {
    background-color: #1e293b;
    border-color: #334155;
    color: #64748b;
}

/* Cancel / Danger Button */
QPushButton#cancelButton {
    background-color: #451a1a;
    border: 1px solid #7f1d1d;
    color: #fca5a5;
    font-weight: 600;
    padding: 9px 18px;
    border-radius: 4px;
}

QPushButton#cancelButton:hover {
    background-color: #7f1d1d;
    color: #ffffff;
}

QPushButton#cancelButton:pressed {
    background-color: #351313;
}

/* Success Button (Open File) */
QPushButton#successButton {
    background-color: #065f46;
    border: 1px solid #059669;
    color: #a7f3d0;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 4px;
}

QPushButton#successButton:hover {
    background-color: #047857;
    color: #ffffff;
}

QPushButton#successButton:pressed {
    background-color: #064e3b;
}

QPushButton#successButton:disabled {
    background-color: #16181d;
    border-color: #262a33;
    color: #4b5563;
}

/* Preset Buttons */
QPushButton#presetButton {
    background-color: #1c1f26;
    border: 1px solid #2d333f;
    padding: 4px 8px;
    font-size: 11px;
    color: #94a3b8;
}

QPushButton#presetButton:hover {
    background-color: #29303d;
    border-color: #38bdf8;
    color: #e0f2fe;
}

/* Progress Bar */
QProgressBar {
    background-color: #16181d;
    border: 1px solid #2d3139;
    border-radius: 3px;
    text-align: center;
    color: #f8fafc;
    font-weight: 600;
    font-size: 12px;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0284c7;
    border-radius: 2px;
}

/* Horizontal Size Slider */
QSlider:horizontal {
    min-height: 24px;
    background: transparent;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #252830;
    border: 1px solid #374151;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #0284c7;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #38bdf8;
    border: 1px solid #0284c7;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #7dd3fc;
    border-color: #38bdf8;
}

QSlider::handle:horizontal:pressed {
    background: #0284c7;
}

QSlider::handle:horizontal:disabled {
    background: #475569;
    border-color: #334155;
}

/* Splitter */
QSplitter {
    background-color: transparent;
}

QSplitter::handle {
    background-color: #1e2128;
    height: 3px;
}

QSplitter::handle:hover {
    background-color: #0284c7;
}

/* Console Log View */
QPlainTextEdit#logConsole, QTextEdit#logConsole {
    background-color: #0f1013;
    border: 1px solid #262930;
    border-radius: 4px;
    padding: 8px;
    font-family: 'Ubuntu Mono', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.4;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #121316;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2b303c;
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #3b4252;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #121316;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #2b303c;
    min-width: 20px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #3b4252;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #14161b;
    border-top: 1px solid #242730;
    color: #64748b;
    font-size: 11px;
}
"""
