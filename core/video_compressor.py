"""
Video compressor module using FFmpeg 2-pass encoding.
Calculates exact target bitrates with safety margins and automatically downscales
resolution when bitrate density falls below critical visual thresholds.
"""

import os
import re
import subprocess
import tempfile
import time
from typing import Callable, Optional, Dict, Any, Tuple
from core.probe import probe_file, get_ffmpeg_executable, format_size, format_duration

# Windows flag to suppress cmd window popup
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class VideoCompressor:
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
        self.active_process: Optional[subprocess.Popen] = None

    def cancel(self):
        """Terminates active FFmpeg process if running."""
        if self.active_process and self.active_process.poll() is None:
            try:
                self.active_process.kill()
            except Exception:
                pass

    def _determine_target_resolution(
        self,
        orig_w: int,
        orig_h: int,
        fps: float,
        video_bitrate_kbps: float,
        mode: str
    ) -> Tuple[Optional[int], str]:
        """
        Determines if video should be downscaled and returns (target_height, explanation).
        target_height = None means keep original resolution.
        """
        if mode == "preserve_res":
            return None, "Preserve original resolution (mode setting)"

        fps_val = fps if fps > 5 else 30.0
        # Calculate Bits Per Pixel (bpp)
        bpp = (video_bitrate_kbps * 1000.0) / (orig_w * orig_h * fps_val)

        # Standard step thresholds
        if mode == "scale_res":
            # Aggressive downscaling to maintain high bpp (>= 0.10)
            if orig_h > 1080 and video_bitrate_kbps < 3500:
                return 1080, "Scale priority: 4K/2K -> 1080p for consistent bitrate"
            elif orig_h >= 1080 and video_bitrate_kbps < 2000:
                return 720, "Scale priority: 1080p -> 720p for high clarity"
            elif orig_h >= 720 and video_bitrate_kbps < 1000:
                return 480, "Scale priority: 720p -> 480p to prevent compression artifacts"
            elif orig_h >= 480 and video_bitrate_kbps < 450:
                return 360, "Scale priority: 480p -> 360p"
            elif orig_h >= 360 and video_bitrate_kbps < 200:
                return 240, "Scale priority: 360p -> 240p"
            return None, "Resolution adequate for allocated bitrate"

        # Mode == 'balanced'
        # Downscale only when bpp falls below acceptable compression limits (< ~0.055)
        if orig_h > 1080 and video_bitrate_kbps < 2800:
            return 1080, f"Low bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 1080p to avoid artifacts"
        elif orig_h >= 1080 and video_bitrate_kbps < 1500:
            return 720, f"Low bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 720p for visual balance"
        elif orig_h >= 720 and video_bitrate_kbps < 750:
            return 480, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 480p for stability"
        elif orig_h >= 480 and video_bitrate_kbps < 320:
            return 360, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 360p"
        elif orig_h >= 360 and video_bitrate_kbps < 160:
            return 240, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 240p"

        return None, "Original resolution maintained (sufficient bpp)"

    def _run_pass(
        self,
        cmd: list,
        duration: float,
        pass_num: int,
        progress_range: Tuple[int, int]
    ) -> Tuple[int, str]:
        """
        Executes an FFmpeg pass with real-time stderr progress parsing.
        """
        ffmpeg_bin = get_ffmpeg_executable()
        self.active_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        stderr_buffer = []
        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        p_start, p_end = progress_range
        last_pct = p_start

        while True:
            if self.is_cancelled():
                self.cancel()
                raise InterruptedError("Operation was cancelled by user.")

            line = self.active_process.stderr.readline()
            if not line and self.active_process.poll() is not None:
                break

            if line:
                stderr_buffer.append(line)
                match = time_pattern.search(line)
                if match and duration > 0:
                    h, m, s = match.groups()
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    ratio = min(1.0, current_sec / duration)
                    current_pct = int(p_start + ratio * (p_end - p_start))
                    if current_pct > last_pct:
                        last_pct = current_pct
                        self.progress(
                            current_pct,
                            f"Pass {pass_num}/2: {format_duration(current_sec)} / {format_duration(duration)} ({current_pct}%)"
                        )

        returncode = self.active_process.wait()
        full_stderr = "".join(stderr_buffer)
        try:
            if self.active_process.stdout:
                self.active_process.stdout.close()
            if self.active_process.stderr:
                self.active_process.stderr.close()
        except Exception:
            pass
        return returncode, full_stderr

    def compress(
        self,
        input_path: str,
        output_path: str,
        target_bytes: int,
        mode: str = "balanced"  # 'balanced', 'preserve_res', 'scale_res'
    ) -> Dict[str, Any]:
        """
        Executes 2-pass FFmpeg video compression to reach target_bytes.
        """
        if self.is_cancelled():
            raise InterruptedError("Operation was cancelled by user.")

        orig_size = os.path.getsize(input_path)
        self.log("INFO", f"Analyzing source video: {os.path.basename(input_path)} ({format_size(orig_size)})")
        self.log("INFO", f"Target size: {format_size(target_bytes)} ({target_bytes} bytes)")

        if orig_size <= target_bytes:
            self.log("WARN", f"File is already smaller than target ({format_size(orig_size)} <= {format_size(target_bytes)}). No compression needed.")
            return {
                "success": True,
                "already_smaller": True,
                "original_size": orig_size,
                "final_size": orig_size,
                "output_path": input_path,
            }

        # Probe input file
        meta = probe_file(input_path)
        duration = meta.get("duration", 0.0)
        orig_w = meta.get("width", 0)
        orig_h = meta.get("height", 0)
        fps = meta.get("fps", 30.0)
        has_audio = meta.get("has_audio", False)

        if duration <= 0:
            raise ValueError(f"Could not determine video duration ({input_path}).")

        self.log(
            "INFO",
            f"Source video parameters: {orig_w}x{orig_h} @ {fps:.1f} fps | "
            f"Duration: {format_duration(duration)} | Audio: {'Present' if has_audio else 'None'}"
        )

        # Target Bitrate Formula:
        safety_margin = 0.95
        total_bitrate_kbps = ((target_bytes * 8.0) / (duration * 1000.0)) * safety_margin

        if total_bitrate_kbps < 40:
            self.log("WARN", f"Calculated total bitrate ({total_bitrate_kbps:.1f} kbps) is extremely low for duration of {format_duration(duration)}.")

        # Audio bitrate allocation
        if has_audio:
            if total_bitrate_kbps >= 2000:
                audio_bitrate_kbps = 128.0
            elif total_bitrate_kbps >= 800:
                audio_bitrate_kbps = 96.0
            elif total_bitrate_kbps >= 400:
                audio_bitrate_kbps = 64.0
            elif total_bitrate_kbps >= 200:
                audio_bitrate_kbps = 48.0
            else:
                audio_bitrate_kbps = 32.0

            # Ensure audio does not take more than 35% of total budget
            max_audio_share = total_bitrate_kbps * 0.35
            if audio_bitrate_kbps > max_audio_share:
                audio_bitrate_kbps = max(24.0, max_audio_share)
        else:
            audio_bitrate_kbps = 0.0

        video_bitrate_kbps = max(20.0, total_bitrate_kbps - audio_bitrate_kbps)

        self.log(
            "INFO",
            f"Bitrate budget: Total: {total_bitrate_kbps:.1f} kbps | "
            f"Video: {video_bitrate_kbps:.1f} kbps | Audio: {audio_bitrate_kbps:.1f} kbps"
        )

        # Resolution scaling decision
        target_h, reason = self._determine_target_resolution(orig_w, orig_h, fps, video_bitrate_kbps, mode)
        self.log("INFO", f"Resolution decision: {reason}")

        video_filters = []
        if target_h and orig_h > 0 and target_h < orig_h:
            # Scale video preserving aspect ratio, ensuring width is divisible by 2 for H.264
            video_filters.append(f"scale=-2:{target_h}")

        vf_arg = ["-vf", ",".join(video_filters)] if video_filters else []

        # Determine Codecs based on output container
        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".webm":
            v_codec = "libvpx-vp9"
            a_codec = "libopus"
        else:
            v_codec = "libx264"
            a_codec = "aac"

        ffmpeg_bin = get_ffmpeg_executable()
        temp_dir = tempfile.mkdtemp(prefix="wz_ffmpeg_")
        passlog_prefix = os.path.join(temp_dir, "pass2_log")
        null_dest = "NUL" if os.name == "nt" else "/dev/null"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        try:
            # PASS 1: Analysis pass
            self.progress(5, "Starting pass 1/2 (frame analysis)...")
            self.log("INFO", f"[PASS 1/2] Video analysis with {v_codec}...")

            cmd_pass1 = [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-i", input_path,
                "-c:v", v_codec,
                "-b:v", f"{int(video_bitrate_kbps)}k",
                "-pass", "1",
                "-passlogfile", passlog_prefix,
                "-an",
                *vf_arg,
                "-f", "null",
                null_dest
            ]

            code1, err1 = self._run_pass(cmd_pass1, duration, pass_num=1, progress_range=(5, 48))
            if code1 != 0:
                self.log("ERROR", f"Error during Pass 1 (code {code1}):\n{err1[-400:]}")
                raise RuntimeError(f"FFmpeg Pass 1 failed with code {code1}. Details: {err1[-200:]}")

            # PASS 2: Final encoding pass with audio
            self.progress(50, "Starting pass 2/2 (final encoding)...")
            self.log("INFO", f"[PASS 2/2] Encoding video and multiplexing {a_codec} audio...")

            cmd_pass2 = [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-i", input_path,
                "-c:v", v_codec,
                "-b:v", f"{int(video_bitrate_kbps)}k",
                "-pass", "2",
                "-passlogfile", passlog_prefix,
                "-preset", "medium",
                *vf_arg
            ]

            if has_audio and audio_bitrate_kbps > 0:
                cmd_pass2.extend(["-c:a", a_codec, "-b:a", f"{int(audio_bitrate_kbps)}k"])
            else:
                cmd_pass2.append("-an")

            cmd_pass2.append(output_path)

            code2, err2 = self._run_pass(cmd_pass2, duration, pass_num=2, progress_range=(50, 98))
            if code2 != 0:
                self.log("ERROR", f"Error during Pass 2 (code {code2}):\n{err2[-400:]}")
                raise RuntimeError(f"FFmpeg Pass 2 failed with code {code2}. Details: {err2[-200:]}")

        finally:
            # Clean up passlog files and temp directory
            try:
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except Exception:
                pass

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Output file was not generated: {output_path}")

        final_size = os.path.getsize(output_path)
        saved_bytes = orig_size - final_size
        pct_saved = (saved_bytes / orig_size) * 100 if orig_size > 0 else 0

        self.progress(100, "Video compression completed successfully!")
        status_tag = "SUCCESS" if final_size <= target_bytes else "WARN"
        self.log(
            status_tag,
            f"Compression finished: {output_path} | Size: {format_size(final_size)} "
            f"({pct_saved:.1f}% saved) | Target: {format_size(target_bytes)}"
        )

        return {
            "success": True,
            "original_size": orig_size,
            "final_size": final_size,
            "output_path": output_path,
            "duration": duration,
            "target_height": target_h,
            "video_bitrate_kbps": video_bitrate_kbps,
            "audio_bitrate_kbps": audio_bitrate_kbps,
            "saved_percentage": pct_saved,
        }
