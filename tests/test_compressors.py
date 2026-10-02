"""
Automated unit and integration test suite for WZ Resizer compressors and probe.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from PIL import Image, ImageDraw

from core.probe import probe_file, get_ffmpeg_executable, format_size, format_duration
from core.image_compressor import ImageCompressor
from core.video_compressor import VideoCompressor
from core.worker import generate_unique_output_path


class TestWZResizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="wz_test_")
        cls.ffmpeg_bin = get_ffmpeg_executable()

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.test_dir)
        except Exception:
            pass

    def test_01_probe_image(self):
        img_path = os.path.join(self.test_dir, "probe_sample.png")
        img = Image.new("RGBA", (800, 600), (255, 0, 0, 255))
        img.save(img_path)

        meta = probe_file(img_path)
        self.assertEqual(meta["type"], "image")
        self.assertEqual(meta["width"], 800)
        self.assertEqual(meta["height"], 600)
        self.assertEqual(meta["format"], "PNG")
        self.assertGreater(meta["size_bytes"], 0)

    def test_02_image_compression_binary_search(self):
        input_jpg = os.path.join(self.test_dir, "large_sample.jpg")
        output_jpg = os.path.join(self.test_dir, "compressed_sample.jpg")

        # Create gradient image with detail so JPEG has data
        img = Image.new("RGB", (2560, 1440))
        draw = ImageDraw.Draw(img)
        for y in range(1440):
            draw.line([(0, y), (2560, y)], fill=(y % 256, (y * 2) % 256, (y * 3) % 256))
        img.save(input_jpg, quality=95)

        orig_size = os.path.getsize(input_jpg)
        target_bytes = 100 * 1024  # 100 KB target

        compressor = ImageCompressor()
        result = compressor.compress(input_jpg, output_jpg, target_bytes, mode="balanced")

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(output_jpg))
        final_size = os.path.getsize(output_jpg)
        self.assertLessEqual(final_size, target_bytes)
        self.assertLess(final_size, orig_size)

    def test_03_image_already_smaller(self):
        small_jpg = os.path.join(self.test_dir, "small_sample.jpg")
        img = Image.new("RGB", (100, 100), (50, 50, 50))
        img.save(small_jpg, quality=60)
        orig_size = os.path.getsize(small_jpg)

        compressor = ImageCompressor()
        result = compressor.compress(
            small_jpg,
            os.path.join(self.test_dir, "wont_be_saved.jpg"),
            target_bytes=orig_size + 10000,
            mode="balanced"
        )
        self.assertTrue(result.get("already_smaller", False))

    def test_04_unique_output_path(self):
        base_file = os.path.join(self.test_dir, "document.mp4")
        with open(base_file, "w") as f:
            f.write("dummy")

        out1 = generate_unique_output_path(base_file)
        self.assertEqual(out1, os.path.join(self.test_dir, "document_compressed.mp4"))

        # Create out1 on disk
        with open(out1, "w") as f:
            f.write("dummy1")

        out2 = generate_unique_output_path(base_file)
        self.assertEqual(out2, os.path.join(self.test_dir, "document_compressed(1).mp4"))

    def test_05_video_probe_and_compression(self):
        in_video = os.path.join(self.test_dir, "test_vid.mp4")
        out_video = os.path.join(self.test_dir, "test_vid_compressed.mp4")

        # Generate a 4-second video
        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=1280x720:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-b:v", "2000k",
            "-c:a", "aac", "-b:a", "128k",
            in_video
        ]
        res = subprocess.run(cmd, capture_output=True)
        self.assertEqual(res.returncode, 0)

        # Test video probe
        meta = probe_file(in_video)
        self.assertEqual(meta["type"], "video")
        self.assertEqual(meta["width"], 1280)
        self.assertEqual(meta["height"], 720)
        self.assertAlmostEqual(meta["duration"], 4.0, delta=0.5)
        self.assertTrue(meta["has_audio"])

        # Target: 180 KB (less than 333 KB input)
        target_bytes = 180 * 1024
        compressor = VideoCompressor()
        result = compressor.compress(in_video, out_video, target_bytes, mode="balanced")

        self.assertTrue(result["success"])
        self.assertFalse(result.get("already_smaller", False))
        self.assertTrue(os.path.exists(out_video))
        final_size = os.path.getsize(out_video)
        self.assertLessEqual(final_size, target_bytes)


if __name__ == "__main__":
    unittest.main()
