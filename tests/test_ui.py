"""
UI integration tests for WZ Resizer verifying slider synchronization,
spinbox bidirectional binding, 1 Byte minimum limit, and full English localization.
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

        # 1. Moving slider to 10 MB (10 * 1024 * 1024 bytes) updates spinbox to 10.00 MB
        ten_mb = 10 * 1024 * 1024
        self.win.size_slider.setValue(ten_mb)
        self.assertAlmostEqual(self.win.size_spinbox.value(), 10.0, places=2)

        # 2. Changing spinbox to 20.00 MB updates slider to 20 MB
        twenty_mb = 20 * 1024 * 1024
        self.win.size_spinbox.setValue(20.0)
        self.assertEqual(self.win.size_slider.value(), twenty_mb)

        # 3. Switching unit to KB
        self.win.unit_combo.setCurrentText("KB")
        self.assertAlmostEqual(self.win.size_spinbox.value(), 20480.0, places=1)

        # 4. Switching unit to B
        self.win.unit_combo.setCurrentText("B")
        self.assertEqual(self.win.size_spinbox.value(), float(twenty_mb))

        # 5. Applying preset 8 MB
        self.win._apply_preset(8.0, "MB")
        self.assertEqual(self.win.size_spinbox.value(), 8.0)
        self.assertEqual(self.win.size_slider.value(), 8 * 1024 * 1024)

    def test_minimum_1_byte_limit(self):
        # Slider minimum must be 1 Byte
        self.assertEqual(self.win.size_slider.minimum(), 1)

        # Dragging slider to minimum (1)
        self.win.size_slider.setValue(1)
        self.assertEqual(self.win._slider_to_bytes(self.win.size_slider.value()), 1)
        self.assertTrue(self.win.slider_info_label.text().startswith("1 B"))

        # Switching to Byte unit and inputting 1 B
        self.win.unit_combo.setCurrentText("B")
        self.win.size_spinbox.setValue(1.0)
        self.assertEqual(self.win._calculate_target_bytes(), 1)
        self.assertEqual(self.win.size_slider.value(), 1)

        # Inputting 500 B
        self.win.size_spinbox.setValue(500.0)
        self.assertEqual(self.win._calculate_target_bytes(), 500)
        self.assertEqual(self.win.size_slider.value(), 500)
        self.assertTrue(self.win.slider_info_label.text().startswith("500 B"))

    def test_file_loaded_dynamic_slider_range(self):
        # 1. Test normal file (e.g. 5 MB)
        meta_5mb = {"size_bytes": 5 * 1024 * 1024, "type": "IMAGE", "format": "PNG", "width": 1920, "height": 1080}
        self.win._on_file_selected("test_file.png", meta_5mb)
        self.assertEqual(self.win.size_slider.minimum(), 1)
        self.assertEqual(self.win.size_slider.maximum(), 5 * 1024 * 1024)

        # Slider can be set down to 1 Byte
        self.win.size_slider.setValue(1)
        self.assertEqual(self.win._slider_to_bytes(1), 1)
        self.assertTrue(self.win.slider_info_label.text().startswith("1 B"))

        # 2. Test large file > 2 GB (e.g. 3.5 GB)
        meta_large = {"size_bytes": 3500000000, "type": "VIDEO", "duration": 120.0, "width": 3840, "height": 2160, "fps": 60.0}
        self.win._on_file_selected("large_video.mp4", meta_large)
        self.assertEqual(self.win.size_slider.minimum(), 1)
        self.assertEqual(self.win._slider_to_bytes(1), 1)
        self.assertEqual(self.win._slider_to_bytes(self.win.size_slider.maximum()), 3500000000)

    def test_video_fps_limiter_ui(self):
        # 1. Default state: No limit
        self.assertEqual(self.win.fps_combo.currentText(), "No limit (Original)")
        self.assertIsNone(self.win._get_selected_max_fps())
        self.assertFalse(self.win.fps_spinbox.isEnabled())

        # 2. Select preset: 30 FPS
        self.win.fps_combo.setCurrentText("30 FPS")
        self.assertEqual(self.win._get_selected_max_fps(), 30.0)
        self.assertEqual(self.win.fps_spinbox.value(), 30)
        self.assertFalse(self.win.fps_spinbox.isEnabled())

        # 3. Select Custom: spinbox enables
        self.win.fps_combo.setCurrentText("Custom...")
        self.assertTrue(self.win.fps_spinbox.isEnabled())
        self.win.fps_spinbox.setValue(45)
        self.assertEqual(self.win._get_selected_max_fps(), 45.0)

        # 4. When an image file is loaded, FPS controls are disabled
        img_meta = {"size_bytes": 100000, "type": "IMAGE", "format": "JPG", "width": 800, "height": 600}
        self.win._on_file_selected("sample.jpg", img_meta)
        self.assertFalse(self.win.fps_combo.isEnabled())
        self.assertFalse(self.win.fps_spinbox.isEnabled())
        self.assertEqual(self.win.fps_info_label.text(), "(Not applicable for images)")

        # 5. When a video file is loaded, FPS controls are enabled and source fps displayed
        vid_meta = {"size_bytes": 1000000, "type": "VIDEO", "duration": 10.0, "width": 1920, "height": 1080, "fps": 60.0}
        self.win._on_file_selected("sample.mp4", vid_meta)
        self.assertTrue(self.win.fps_combo.isEnabled())
        self.assertIn("60.0 fps", self.win.fps_info_label.text())

    def test_open_buttons_state(self):
        self.assertFalse(self.win.open_file_btn.isEnabled())
        self.assertFalse(self.win.open_folder_btn.isEnabled())
        self.assertEqual(self.win.open_file_btn.text(), "Open Compressed File")
        self.assertEqual(self.win.open_folder_btn.text(), "Open Folder")


if __name__ == "__main__":
    unittest.main()
