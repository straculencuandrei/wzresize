"""
UI integration tests for WZ Resizer verifying slider synchronization,
spinbox bidirectional binding, and full English localization.
"""

import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


class TestMainWindowUI(unittest.TestCase):
    def setUp(self):
        self.win = MainWindow()

    def tearDown(self):
        self.win.close()

    def test_slider_spinbox_bidirectional_sync(self):
        # Default unit is MB
        self.win.unit_combo.setCurrentText("MB")

        # 1. Moving slider to 10240 KB (10 MB) updates spinbox to 10.00 MB
        self.win.size_slider.setValue(10240)
        self.assertAlmostEqual(self.win.size_spinbox.value(), 10.0, places=2)

        # 2. Changing spinbox to 20.00 MB updates slider to 20480 KB
        self.win.size_spinbox.setValue(20.0)
        self.assertEqual(self.win.size_slider.value(), 20480)

        # 3. Switching unit to KB
        self.win.unit_combo.setCurrentText("KB")
        self.assertAlmostEqual(self.win.size_spinbox.value(), 20480.0, places=1)

        # 4. Applying preset 8 MB
        self.win._apply_preset(8.0, "MB")
        self.assertEqual(self.win.size_spinbox.value(), 8.0)
        self.assertEqual(self.win.size_slider.value(), 8192)

    def test_english_labels_present(self):
        self.assertEqual(self.win.start_btn.text(), "Process / Compress")
        self.assertEqual(self.win.cancel_btn.text(), "Cancel")
        self.assertIn("Target Size", self.win.windowTitle())
        self.assertEqual(self.win.radio_balanced.text(), "Balanced (downscale + quality)")


if __name__ == "__main__":
    unittest.main()
