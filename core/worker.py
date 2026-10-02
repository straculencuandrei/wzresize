"""
Worker thread for running image and video compression asynchronously.
Keeps UI fluid and responsive with PyQt6 signals.
"""

import os
import traceback
from typing import Optional, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal

from core.probe import probe_file, format_size
from core.image_compressor import ImageCompressor
from core.video_compressor import VideoCompressor


def generate_unique_output_path(input_path: str, custom_dir: Optional[str] = None, suffix: str = "_compressed") -> str:
    """
    Generates a non-conflicting output file path with the specified suffix.
    Guarantees the original file is NEVER overwritten.
    """
    dirname, filename = os.path.split(input_path)
    if custom_dir and os.path.isdir(custom_dir):
        target_dir = custom_dir
    else:
        target_dir = dirname

    base, ext = os.path.splitext(filename)
    candidate = os.path.join(target_dir, f"{base}{suffix}{ext}")

    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(target_dir, f"{base}{suffix}({counter}){ext}")
        counter += 1

    return candidate


class CompressionWorker(QThread):
    # Signals to communicate with the UI thread
    sig_log = pyqtSignal(str, str)         # level ('INFO', 'SUCCESS', 'WARN', 'ERROR'), message
    sig_progress = pyqtSignal(int, str)    # percentage (0-100), status text
    sig_finished = pyqtSignal(bool, str, dict)  # success, message, stats dict
    sig_error = pyqtSignal(str, int)       # error message, code

    def __init__(
        self,
        input_path: str,
        target_bytes: int,
        mode: str = "balanced",
        custom_output_dir: Optional[str] = None,
        max_fps: Optional[float] = None,
        parent=None
    ):
        super().__init__(parent)
        self.input_path = input_path
        self.target_bytes = target_bytes
        self.mode = mode
        self.custom_output_dir = custom_output_dir
        self.max_fps = max_fps
        self._is_cancelled = False

        self.img_compressor: Optional[ImageCompressor] = None
        self.vid_compressor: Optional[VideoCompressor] = None

    def cancel(self):
        """Requests cancellation of ongoing compression."""
        self._is_cancelled = True
        if self.vid_compressor:
            self.vid_compressor.cancel()

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _emit_log(self, level: str, message: str):
        self.sig_log.emit(level, message)

    def _emit_progress(self, pct: int, status: str):
        self.sig_progress.emit(pct, status)

    def run(self):
        try:
            if not os.path.isfile(self.input_path):
                self._emit_log("ERROR", f"Source file not found: {self.input_path}")
                self.sig_error.emit("Source file is missing", 404)
                return

            orig_size = os.path.getsize(self.input_path)
            self._emit_log("INFO", f"Initializing processing for: {os.path.basename(self.input_path)}")
            self._emit_log("INFO", f"Current size: {format_size(orig_size)} ({orig_size} bytes)")
            self._emit_log("INFO", f"Target size: {format_size(self.target_bytes)} ({self.target_bytes} bytes)")

            # Check if already within target constraint
            if orig_size <= self.target_bytes:
                msg = (
                    f"Selected file is already smaller than the specified target "
                    f"({format_size(orig_size)} <= {format_size(self.target_bytes)}). "
                    f"Completed without changes."
                )
                self._emit_log("WARN", msg)
                self._emit_progress(100, "File already complies with target size!")
                self.sig_finished.emit(True, msg, {
                    "already_smaller": True,
                    "original_size": orig_size,
                    "final_size": orig_size,
                    "output_path": self.input_path,
                })
                return

            # Probe media type
            meta = probe_file(self.input_path)
            media_type = meta.get("type", "unknown")
            output_path = generate_unique_output_path(self.input_path, self.custom_output_dir)

            self._emit_log("INFO", f"Detected media type: {media_type.upper()} ({meta.get('format', 'UNKNOWN')})")
            self._emit_log("INFO", f"Safe destination (no overwrite): {output_path}")

            if media_type == "image":
                self.img_compressor = ImageCompressor(
                    log_callback=self._emit_log,
                    progress_callback=self._emit_progress,
                    cancel_check=self.is_cancelled,
                )
                res = self.img_compressor.compress(
                    input_path=self.input_path,
                    output_path=output_path,
                    target_bytes=self.target_bytes,
                    mode=self.mode,
                )
                if self.is_cancelled():
                    self._emit_log("WARN", "Image processing was cancelled.")
                    self.sig_error.emit("Cancelled by user", 1)
                    return

                self.sig_finished.emit(True, "Image compression completed successfully!", res)

            elif media_type == "video":
                self.vid_compressor = VideoCompressor(
                    log_callback=self._emit_log,
                    progress_callback=self._emit_progress,
                    cancel_check=self.is_cancelled,
                )
                res = self.vid_compressor.compress(
                    input_path=self.input_path,
                    output_path=output_path,
                    target_bytes=self.target_bytes,
                    mode=self.mode,
                    max_fps=self.max_fps,
                )
                if self.is_cancelled():
                    self._emit_log("WARN", "Video processing was cancelled.")
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except Exception:
                            pass
                    self.sig_error.emit("Cancelled by user", 1)
                    return

                self.sig_finished.emit(True, "Video compression completed successfully!", res)

            else:
                err_msg = f"Unsupported file format: {meta.get('extension', 'unknown')}"
                self._emit_log("ERROR", err_msg)
                self.sig_error.emit(err_msg, 415)

        except InterruptedError:
            self._emit_log("WARN", "Operation was cancelled by user.")
            self.sig_error.emit("Operation cancelled", 130)
        except Exception as e:
            tb = traceback.format_exc()
            err_msg = f"Unexpected error during processing: {str(e)}"
            self._emit_log("ERROR", f"{err_msg}\n{tb}")
            self.sig_error.emit(str(e), 500)
