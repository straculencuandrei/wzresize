"""
Video compressor module using FFmpeg 2-pass encoding.
Calculates exact target bitrates with safety margins and automatically downscales
resolution when bitrate density falls below critical visual thresholds.
"""

import os
import re
import subprocess
import tempfile
from typing import Callable, Optional, Dict, Any, Tuple
from core.probe import probe_file, get_ffmpeg_executable, format_size, format_duration

# Windows flag to suppress cmd window popup
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


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
        proc = self.active_process
        if proc and proc.poll() is None:
            try:
                proc.kill()
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
        # Normalize bitrate to a 30 fps baseline so lower FPS caps retain higher resolution
        effective_bitrate = video_bitrate_kbps * (30.0 / fps_val)

        if mode == "scale_res":
            # Aggressive downscaling to maintain high bits-per-pixel
            tiers = [
                (240, 200, "Scale priority: -> 240p"),
                (360, 450, "Scale priority: -> 360p"),
                (480, 1000, "Scale priority: -> 480p to prevent compression artifacts"),
                (720, 2000, "Scale priority: -> 720p for high clarity"),
                (1080, 3500, "Scale priority: -> 1080p for consistent bitrate"),
            ]
            default_msg = "Resolution adequate for allocated bitrate"
        else:
            # Mode == 'balanced': downscale only when bpp falls below comfortable thresholds
            tiers = [
                (240, 160, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 240p"),
                (360, 320, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 360p"),
                (480, 750, f"Critical bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 480p for stability"),
                (720, 1500, f"Low bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 720p for visual balance"),
                (1080, 2800, f"Low bitrate ({video_bitrate_kbps:.0f} kbps): Downscaling to 1080p to avoid artifacts"),
            ]
            default_msg = "Original resolution maintained (sufficient bpp)"

        for target_h, min_kbps, msg in tiers:
            if orig_h > target_h and effective_bitrate < min_kbps:
                return target_h, msg

        return None, default_msg

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
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        self.active_process = proc

        stderr_buffer = []
        p_start, p_end = progress_range
        last_pct = p_start

        try:
            while True:
                if self.is_cancelled():
                    self.cancel()
                    raise InterruptedError("Operation was cancelled by user.")

                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break

                if line:
                    stderr_buffer.append(line)
                    match = _TIME_PATTERN.search(line)
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

            returncode = proc.wait()
            return returncode, "".join(stderr_buffer)
        finally:
            self.active_process = None
            try:
                if proc.stderr:
                    proc.stderr.close()
            except Exception:
                pass

    def compress(
        self,
        input_path: str,
        output_path: str,
        target_bytes: int,
        mode: str = "balanced",  # 'balanced', 'preserve_res', 'scale_res'
        max_fps: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes 2-pass FFmpeg video compression to reach target_bytes.
        Supports max_fps limit to conserve bitrate and enhance visual quality.
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

        # Framerate Limiter evaluation
        effective_fps = fps
        fps_filter_applied = False
        if max_fps and max_fps > 0:
            if fps > (max_fps + 0.1):
                effective_fps = max_fps
                fps_filter_applied = True
                self.log("INFO", f"FPS Limiter active: Capping framerate from {fps:.1f} fps to {max_fps:.1f} fps")
            else:
                self.log("INFO", f"FPS Limiter: Source framerate ({fps:.1f} fps) is within limit ({max_fps:.1f} fps)")
        else:
            self.log("INFO", f"FPS Limiter: Disabled (retaining original {fps:.1f} fps)")

        self.log(
            "INFO",
            f"Source video parameters: {orig_w}x{orig_h} @ {fps:.1f} fps (effective: {effective_fps:.1f} fps) | "
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
                audio_floor = 12.0 if total_bitrate_kbps < 70 else 24.0
                audio_bitrate_kbps = max(audio_floor, min(audio_bitrate_kbps, max_audio_share))
        else:
            audio_bitrate_kbps = 0.0

        video_bitrate_kbps = max(10.0, total_bitrate_kbps - audio_bitrate_kbps)

        self.log(
            "INFO",
            f"Bitrate budget: Total: {total_bitrate_kbps:.1f} kbps | "
            f"Video: {video_bitrate_kbps:.1f} kbps | Audio: {audio_bitrate_kbps:.1f} kbps"
        )

        # Resolution scaling decision
        target_h, reason = self._determine_target_resolution(orig_w, orig_h, effective_fps, video_bitrate_kbps, mode)
        self.log("INFO", f"Resolution decision: {reason}")

        # Determine Codecs based on output container
        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".webm":
            v_codec = "libvpx-vp9"
            a_codec = "libopus"
            pass1_codec_args = ["-deadline", "good", "-cpu-used", "4"]
            pass2_codec_args = ["-deadline", "good", "-cpu-used", "2"]
        else:
            v_codec = "libx264"
            a_codec = "aac"
            pass1_codec_args = ["-preset", "medium", "-pix_fmt", "yuv420p"]
            pass2_codec_args = ["-preset", "medium", "-pix_fmt", "yuv420p"]
            if ext in (".mp4", ".mov", ".m4v"):
                pass2_codec_args.extend(["-movflags", "+faststart"])

        video_filters = []
        if fps_filter_applied:
            video_filters.append(f"fps=fps={max_fps}")

        if target_h and orig_h > 0 and target_h < orig_h:
            # Scale video preserving aspect ratio, ensuring width is divisible by 2 for H.264/yuv420p
            video_filters.append(f"scale=-2:{target_h}")
        elif v_codec == "libx264" and (orig_w % 2 != 0 or orig_h % 2 != 0):
            video_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        vf_arg = ["-vf", ",".join(video_filters)] if video_filters else []
        v_bitrate_arg = f"{max(1, int(video_bitrate_kbps))}k"

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
                "-b:v", v_bitrate_arg,
                "-pass", "1",
                "-passlogfile", passlog_prefix,
                *pass1_codec_args,
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
                "-b:v", v_bitrate_arg,
                "-pass", "2",
                "-passlogfile", passlog_prefix,
                *pass2_codec_args,
                *vf_arg
            ]

            if has_audio and audio_bitrate_kbps > 0:
                cmd_pass2.extend(["-c:a", a_codec, "-b:a", f"{max(8, int(audio_bitrate_kbps))}k"])
                if audio_bitrate_kbps <= 48:
                    cmd_pass2.extend(["-ac", "1"])
            else:
                cmd_pass2.append("-an")

            cmd_pass2.append(output_path)

            code2, err2 = self._run_pass(cmd_pass2, duration, pass_num=2, progress_range=(50, 98))
            if code2 != 0:
                self.log("ERROR", f"Error during Pass 2 (code {code2}):\n{err2[-400:]}")
                raise RuntimeError(f"FFmpeg Pass 2 failed with code {code2}. Details: {err2[-200:]}")

        except BaseException:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise

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
            "fps": effective_fps,
            "fps_limited": fps_filter_applied,
            "video_bitrate_kbps": video_bitrate_kbps,
            "audio_bitrate_kbps": audio_bitrate_kbps,
            "saved_percentage": pct_saved,
        }
