"""
Image compressor module using Pillow.
Implements binary search for quality optimization and progressive Lanczos downscaling
to reach an exact target file size in bytes.
"""

import io
import math
import os
from typing import Callable, Optional, Tuple, Dict, Any
from PIL import Image, ImageOps


class ImageCompressor:
    def __init__(
        self,
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        """
        :param log_callback: Function accepting (level, message) where level is 'INFO', 'SUCCESS', 'WARN', 'ERROR'.
        :param progress_callback: Function accepting (percentage [0-100], status_text).
        :param cancel_check: Function returning True if operation was cancelled by user.
        """
        self.log = log_callback or (lambda lvl, msg: None)
        self.progress = progress_callback or (lambda pct, msg: None)
        self.is_cancelled = cancel_check or (lambda: False)

    def _test_save(self, img: Image.Image, fmt: str, quality: int, optimize: bool = True) -> bytes:
        """Saves image to memory buffer and returns bytes."""
        buf = io.BytesIO()
        fmt_upper = fmt.upper()

        if fmt_upper in ("JPEG", "JPG"):
            # Ensure RGB mode for JPEG (convert RGBA to RGB on white background)
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if "A" in img.mode:
                    rgb_img.paste(img, mask=img.split()[-1])
                else:
                    rgb_img.paste(img)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img.save(
                buf,
                format="JPEG",
                quality=quality,
                optimize=optimize,
                progressive=True,
            )
        elif fmt_upper == "WEBP":
            img.save(
                buf,
                format="WEBP",
                quality=quality,
                method=6,
            )
        elif fmt_upper == "PNG":
            # For PNG, quality parameter in Pillow is typically ignored unless quantizing
            img.save(
                buf,
                format="PNG",
                optimize=True,
                compress_level=9,
            )
        else:
            # Fallback format
            img.save(buf, format=fmt_upper, optimize=optimize)

        return buf.getvalue()

    def compress(
        self,
        input_path: str,
        output_path: str,
        target_bytes: int,
        mode: str = "balanced"  # 'balanced', 'preserve_res', 'scale_res'
    ) -> Dict[str, Any]:
        """
        Compresses input image to output_path such that os.path.getsize(output_path) <= target_bytes.
        Returns compression result statistics.
        """
        if self.is_cancelled():
            raise InterruptedError("Operation was cancelled by user.")

        orig_size = os.path.getsize(input_path)
        self.log("INFO", f"Opening image file: {os.path.basename(input_path)} ({orig_size / 1024:.1f} KB)")
        self.log("INFO", f"Maximum target size: {target_bytes / 1024:.1f} KB | Mode: {mode}")

        if orig_size <= target_bytes:
            self.log("WARN", f"File is already smaller than target ({orig_size} <= {target_bytes} bytes). No compression needed.")
            return {
                "success": True,
                "already_smaller": True,
                "original_size": orig_size,
                "final_size": orig_size,
                "output_path": input_path,
            }

        # Open image and correct EXIF orientation if present
        with Image.open(input_path) as raw_img:
            img = ImageOps.exif_transpose(raw_img)
            # Create a copy in memory so original file handle is released
            img = img.copy()

        orig_w, orig_h = img.size
        ext = os.path.splitext(output_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            fmt = "JPEG"
        elif ext == ".webp":
            fmt = "WEBP"
        elif ext == ".png":
            fmt = "PNG"
        else:
            fmt = img.format or "JPEG"

        self.log("INFO", f"Source resolution: {orig_w}x{orig_h} | Target format: {fmt}")
        self.progress(10, "Initializing parameter optimization...")

        current_img = img
        current_w, current_h = orig_w, orig_h
        best_data: Optional[bytes] = None
        best_quality = 95
        best_scale = 1.0

        # Parameter boundaries based on mode
        if mode == "preserve_res":
            min_quality = 12
            allow_downscale = False
        elif mode == "scale_res":
            min_quality = 70  # Keep high quality, downscale resolution first
            allow_downscale = True
        else:  # 'balanced'
            min_quality = 30
            allow_downscale = True

        iteration = 0
        max_iterations = 25

        while iteration < max_iterations:
            if self.is_cancelled():
                raise InterruptedError("Operation was cancelled by user.")

            iteration += 1
            progress_val = min(90, 15 + int((iteration / max_iterations) * 75))
            self.progress(progress_val, f"Iteration {iteration}: Testing at {current_w}x{current_h}...")

            # Special case for PNG:
            if fmt == "PNG":
                # First try standard PNG
                test_bytes = self._test_save(current_img, fmt, quality=95)
                if len(test_bytes) <= target_bytes:
                    best_data = test_bytes
                    break

                # If still too large and RGBA/RGB, try quantization (palette 256 colors)
                if mode != "preserve_res" or allow_downscale:
                    try:
                        quant_img = current_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                        buf_q = io.BytesIO()
                        quant_img.save(buf_q, format="PNG", optimize=True)
                        q_data = buf_q.getvalue()
                        if len(q_data) <= target_bytes:
                            best_data = q_data
                            current_img = quant_img
                            break
                    except Exception:
                        pass

                # If PNG cannot hit target and downscaling is not allowed:
                if not allow_downscale:
                    best_data = test_bytes
                    self.log("WARN", "PNG format is lossless. Without resolution downscaling, target size cannot be reached.")
                    break

                # Calculate downscale factor for PNG
                ratio = math.sqrt(target_bytes / len(test_bytes)) * 0.92
                ratio = max(0.2, min(0.92, ratio))
                new_w = max(16, int(current_w * ratio))
                new_h = max(16, int(current_h * ratio))

                if new_w == current_w and new_h == current_h:
                    new_w = max(16, int(current_w * 0.85))
                    new_h = max(16, int(current_h * 0.85))

                self.log("INFO", f"Lanczos downscaling PNG: {current_w}x{current_h} -> {new_w}x{new_h}")
                current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                current_w, current_h = new_w, new_h
                continue

            # Binary search on quality for lossy formats (JPEG, WEBP)
            low_q = min_quality
            high_q = 95
            found_quality_data: Optional[bytes] = None
            found_q = None

            # Test high quality first
            high_bytes = self._test_save(current_img, fmt, quality=high_q)
            if len(high_bytes) <= target_bytes:
                best_data = high_bytes
                best_quality = high_q
                break

            # Test min quality to check feasibility at current resolution
            low_bytes = self._test_save(current_img, fmt, quality=low_q)
            if len(low_bytes) <= target_bytes:
                # Target is reachable within [low_q, high_q] via binary search!
                found_quality_data = low_bytes
                found_q = low_q

                while low_q <= high_q:
                    mid_q = (low_q + high_q) // 2
                    mid_bytes = self._test_save(current_img, fmt, quality=mid_q)
                    mid_len = len(mid_bytes)

                    if mid_len <= target_bytes:
                        found_quality_data = mid_bytes
                        found_q = mid_q
                        # Try higher quality to get best visual fidelity
                        low_q = mid_q + 1
                    else:
                        # Too large, search lower quality
                        high_q = mid_q - 1

                best_data = found_quality_data
                best_quality = found_q
                self.log("INFO", f"Optimal parameters found: Quality {best_quality}% at {current_w}x{current_h} ({len(best_data) / 1024:.1f} KB)")
                break
            else:
                # Even min_quality exceeds target size!
                if not allow_downscale:
                    # User requested 'preserve_res', so we take the lowest possible quality
                    best_data = low_bytes
                    best_quality = low_q
                    self.log("WARN", f"At original resolution, minimum quality ({min_quality}%) yields {len(low_bytes)/1024:.1f} KB (exceeds target).")
                    break

                # Downscale resolution
                current_bytes_len = len(low_bytes)
                ratio = math.sqrt(target_bytes / current_bytes_len) * 0.92
                ratio = max(0.15, min(0.90, ratio))

                new_w = max(16, int(current_w * ratio))
                new_h = max(16, int(current_h * ratio))

                if new_w == current_w and new_h == current_h:
                    new_w = max(16, int(current_w * 0.8))
                    new_h = max(16, int(current_h * 0.8))

                self.log("INFO", f"Downscaling resolution (Lanczos): {current_w}x{current_h} -> {new_w}x{new_h} (quality {min_quality}%)")
                current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                current_w, current_h = new_w, new_h

        # Fallback if no iteration set best_data
        if best_data is None:
            best_data = self._test_save(current_img, fmt, quality=min_quality)

        # Write to destination file atomically
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(best_data)

        final_size = len(best_data)
        saved_bytes = orig_size - final_size
        pct_saved = (saved_bytes / orig_size) * 100 if orig_size > 0 else 0

        self.progress(100, "Image compression completed!")
        self.log(
            "SUCCESS" if final_size <= target_bytes else "WARN",
            f"Saved: {output_path} | Size: {final_size / 1024:.1f} KB "
            f"({pct_saved:.1f}% saved) | Resolution: {current_w}x{current_h}"
        )

        return {
            "success": True,
            "original_size": orig_size,
            "final_size": final_size,
            "output_path": output_path,
            "dimensions": (current_w, current_h),
            "quality": best_quality,
            "saved_percentage": pct_saved,
        }
