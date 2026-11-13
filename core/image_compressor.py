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


_LOSSY_QUALITY_FORMATS = {"JPEG", "JPG", "WEBP"}


def _prepare_rgb_for_jpeg(img: Image.Image) -> Image.Image:
    """Converts any image mode to RGB (compositing alpha onto white) once."""
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA", "P"):
        if img.mode == "P":
            img = img.convert("RGBA")
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        if "A" in img.mode:
            rgb_img.paste(img, mask=img.split()[-1])
        else:
            rgb_img.paste(img)
        return rgb_img
    return img.convert("RGB")


def _compute_downscaled_dims(current_w: int, current_h: int, ratio: float, min_dim: int = 16) -> Tuple[int, int]:
    """Computes downscaled dimensions clamped to min_dim while ensuring shrinkage when possible."""
    new_w = max(min_dim, int(current_w * ratio))
    new_h = max(min_dim, int(current_h * ratio))
    if new_w == current_w and new_h == current_h:
        new_w = max(min_dim, int(current_w * 0.8))
        new_h = max(min_dim, int(current_h * 0.8))
    return new_w, new_h


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
            rgb_img = _prepare_rgb_for_jpeg(img)
            rgb_img.save(
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
            img.save(
                buf,
                format="PNG",
                optimize=True,
                compress_level=9,
            )
        else:
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
            transposed = ImageOps.exif_transpose(raw_img)
            img = raw_img.copy() if transposed is raw_img else transposed

        orig_w, orig_h = img.size
        ext = os.path.splitext(output_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            fmt = "JPEG"
        elif ext == ".webp":
            fmt = "WEBP"
        elif ext == ".png":
            fmt = "PNG"
        else:
            fmt = (img.format or "JPEG").upper()

        # Pre-convert to RGB once for JPEG so binary-search probes don't repeat alpha compositing
        if fmt == "JPEG" and img.mode != "RGB":
            img = _prepare_rgb_for_jpeg(img)

        self.log("INFO", f"Source resolution: {orig_w}x{orig_h} | Target format: {fmt}")
        self.progress(10, "Initializing parameter optimization...")

        current_img = img
        current_w, current_h = orig_w, orig_h
        best_data: Optional[bytes] = None
        best_quality = 95
        smallest_candidate: Optional[Tuple[bytes, Tuple[int, int], int]] = None

        def _record_candidate(data: bytes, dims: Tuple[int, int], q: int) -> None:
            nonlocal smallest_candidate
            if smallest_candidate is None or len(data) < len(smallest_candidate[0]):
                smallest_candidate = (data, dims, q)

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

        is_lossy_quality = fmt in _LOSSY_QUALITY_FORMATS
        iteration = 0
        max_iterations = 25

        while iteration < max_iterations:
            if self.is_cancelled():
                raise InterruptedError("Operation was cancelled by user.")

            iteration += 1
            progress_val = min(90, 15 + int((iteration / max_iterations) * 75))
            self.progress(progress_val, f"Iteration {iteration}: Testing at {current_w}x{current_h}...")

            if not is_lossy_quality:
                # Lossless / non-quality formats (PNG, BMP, TIFF, TGA, etc.)
                test_bytes = self._test_save(current_img, fmt, quality=95)
                _record_candidate(test_bytes, (current_w, current_h), 95)
                if len(test_bytes) <= target_bytes:
                    best_data = test_bytes
                    break

                ref_bytes_len = len(test_bytes)

                # For PNG, try adaptive/fastoctree 256-color palette quantization (preserves resolution)
                if fmt == "PNG" and current_img.mode != "P":
                    try:
                        if current_img.mode == "RGBA":
                            quant_img = current_img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                        else:
                            quant_img = current_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                        buf_q = io.BytesIO()
                        quant_img.save(buf_q, format="PNG", optimize=True, compress_level=9)
                        q_data = buf_q.getvalue()
                        _record_candidate(q_data, (current_w, current_h), 95)
                        if len(q_data) <= target_bytes:
                            best_data = q_data
                            break
                        ref_bytes_len = min(ref_bytes_len, len(q_data))
                    except Exception:
                        pass

                if not allow_downscale:
                    best_data = smallest_candidate[0]
                    self.log("WARN", f"{fmt} format is lossless. Without resolution downscaling, target size cannot be reached.")
                    break

                ratio = max(0.2, min(0.92, math.sqrt(target_bytes / ref_bytes_len) * 0.92))
                new_w, new_h = _compute_downscaled_dims(current_w, current_h, ratio)
                if new_w == current_w and new_h == current_h:
                    self.log("WARN", f"Reached minimum resolution floor ({current_w}x{current_h}); stopping downscale.")
                    break

                self.log("INFO", f"Lanczos downscaling {fmt}: {current_w}x{current_h} -> {new_w}x{new_h}")
                current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                current_w, current_h = new_w, new_h
                continue

            # Lossy formats (JPEG, WEBP): test min_quality first if a big reduction is needed
            high_q = 95
            low_q = min_quality
            test_high_first = (not allow_downscale) or (iteration == 1 and orig_size <= target_bytes * 2)

            if test_high_first:
                high_bytes = self._test_save(current_img, fmt, quality=high_q)
                _record_candidate(high_bytes, (current_w, current_h), high_q)
                if len(high_bytes) <= target_bytes:
                    best_data = high_bytes
                    best_quality = high_q
                    break

                low_bytes = self._test_save(current_img, fmt, quality=low_q)
                _record_candidate(low_bytes, (current_w, current_h), low_q)
                low_fits = len(low_bytes) <= target_bytes
            else:
                low_bytes = self._test_save(current_img, fmt, quality=low_q)
                _record_candidate(low_bytes, (current_w, current_h), low_q)
                low_fits = len(low_bytes) <= target_bytes
                if low_fits and high_q > low_q:
                    high_bytes = self._test_save(current_img, fmt, quality=high_q)
                    _record_candidate(high_bytes, (current_w, current_h), high_q)
                    if len(high_bytes) <= target_bytes:
                        best_data = high_bytes
                        best_quality = high_q
                        break

            if low_fits:
                # Target is reachable within [low_q, high_q - 1] via binary search
                found_quality_data = low_bytes
                found_q = low_q
                search_low = low_q + 1
                search_high = high_q - 1

                while search_low <= search_high:
                    if self.is_cancelled():
                        raise InterruptedError("Operation was cancelled by user.")
                    mid_q = (search_low + search_high) // 2
                    mid_bytes = self._test_save(current_img, fmt, quality=mid_q)
                    _record_candidate(mid_bytes, (current_w, current_h), mid_q)

                    if len(mid_bytes) <= target_bytes:
                        found_quality_data = mid_bytes
                        found_q = mid_q
                        search_low = mid_q + 1
                    else:
                        search_high = mid_q - 1

                best_data = found_quality_data
                best_quality = found_q
                self.log("INFO", f"Optimal parameters found: Quality {best_quality}% at {current_w}x{current_h} ({len(best_data) / 1024:.1f} KB)")
                break

            # Even min_quality exceeds target size
            if not allow_downscale:
                best_data = low_bytes
                best_quality = low_q
                self.log("WARN", f"At original resolution, minimum quality ({min_quality}%) yields {len(low_bytes)/1024:.1f} KB (exceeds target).")
                break

            current_bytes_len = len(low_bytes)
            ratio = max(0.15, min(0.90, math.sqrt(target_bytes / current_bytes_len) * 0.92))
            new_w, new_h = _compute_downscaled_dims(current_w, current_h, ratio)

            if new_w == current_w and new_h == current_h:
                self.log("WARN", f"Reached minimum resolution floor ({current_w}x{current_h}); target size ({target_bytes} B) cannot be reached.")
                break

            self.log("INFO", f"Downscaling resolution (Lanczos): {current_w}x{current_h} -> {new_w}x{new_h} (quality {min_quality}%)")
            current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            current_w, current_h = new_w, new_h

        # Fallback to smallest candidate produced if target could not be met
        if best_data is None:
            if smallest_candidate is not None:
                best_data, (current_w, current_h), best_quality = smallest_candidate
            else:
                best_data = self._test_save(current_img, fmt, quality=min_quality)

        # Write to destination file
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
