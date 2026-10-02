"""
Probe module for extracting media metadata (images and videos).
Utilizes Pillow for images and FFmpeg for video probing.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, Any, Optional
from PIL import Image

try:
    import imageio_ffmpeg
    DEFAULT_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    DEFAULT_FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"


def get_ffmpeg_executable() -> str:
    """Find and return the path to the ffmpeg executable."""
    if DEFAULT_FFMPEG_PATH and os.path.exists(DEFAULT_FFMPEG_PATH):
        return DEFAULT_FFMPEG_PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    return "ffmpeg"


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tga"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", ".wmv", ".m4v"}


def probe_file(file_path: str) -> Dict[str, Any]:
    """
    Extracts metadata from an image or video file.
    Returns a dictionary with comprehensive media specifications.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    size_bytes = os.path.getsize(file_path)

    metadata: Dict[str, Any] = {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "extension": ext,
        "size_bytes": size_bytes,
        "type": "unknown",
        "format": ext.lstrip(".").upper(),
        "width": 0,
        "height": 0,
        "duration": 0.0,
        "fps": 0.0,
        "has_audio": False,
        "video_codec": "",
        "audio_codec": "",
        "bitrate_kbps": 0.0
    }

    if ext in IMAGE_EXTENSIONS:
        metadata["type"] = "image"
        try:
            with Image.open(file_path) as img:
                metadata["width"], metadata["height"] = img.size
                metadata["format"] = img.format or ext.lstrip(".").upper()
                metadata["mode"] = img.mode
            return metadata
        except Exception as e:
            # Fallback if Pillow fails
            metadata["error"] = str(e)

    if ext in VIDEO_EXTENSIONS or metadata["type"] == "unknown":
        # Attempt video probe via ffmpeg
        ffmpeg_bin = get_ffmpeg_executable()
        try:
            res = subprocess.run(
                [ffmpeg_bin, "-hide_banner", "-i", file_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10
            )
            stderr = res.stderr

            # Check if duration exists
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
            if dur_match:
                hours, minutes, seconds = dur_match.groups()
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                metadata["duration"] = total_seconds
                metadata["type"] = "video"
                if total_seconds > 0:
                    metadata["bitrate_kbps"] = (size_bytes * 8) / (total_seconds * 1000)

            # Check video stream
            v_match = re.search(r"Stream #\d+:\d+.*?: Video: ([^,\n]+).*?,\s*(\d{2,5})x(\d{2,5})", stderr)
            if v_match:
                metadata["type"] = "video"
                metadata["video_codec"] = v_match.group(1).strip()
                metadata["width"] = int(v_match.group(2))
                metadata["height"] = int(v_match.group(3))

                # Check fps
                fps_match = re.search(r",\s*(\d+(?:\.\d+)?)\s*fps", stderr)
                if fps_match:
                    metadata["fps"] = float(fps_match.group(1))

            # Check audio stream
            a_match = re.search(r"Stream #\d+:\d+.*?: Audio: ([^,\n]+)", stderr)
            if a_match:
                metadata["has_audio"] = True
                metadata["audio_codec"] = a_match.group(1).strip()

            if metadata["type"] == "video":
                return metadata

        except Exception as e:
            metadata["error"] = str(e)

    # Fallback to image test if not caught yet
    try:
        with Image.open(file_path) as img:
            metadata["type"] = "image"
            metadata["width"], metadata["height"] = img.size
            metadata["format"] = img.format or ext.lstrip(".").upper()
            metadata["mode"] = img.mode
            return metadata
    except Exception:
        pass

    return metadata


def format_size(bytes_val: int) -> str:
    """Format bytes into readable string (B, KB, MB, GB)."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    s = int(round(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"
