# WZ Resizer — Target Size Compressor

A complete, utilitarian, high-performance desktop application built with **Python**, **PyQt6**, **Pillow**, and **FFmpeg**. Enables automated resizing and compression of images and video files down to an exact specified target file size in **MB**, **KB**, or **B** (minimum **1 Byte**) (e.g., *"bring the file under 15 MB"* or *"compress to 8 MB for Discord"*).

---

## Key Features

### 1. Utilitarian Interface & Responsive Design
- **Minimalist Design:** Free of modern glow effects, heavy shadows, wasteful animations, or transparency patches. Zero bloat, instant rendering, and low latency.
- **Typography:** Global application font is **Ubuntu** (packaged in the `fonts/` directory with automatic fallback to system sans-serif).
- **Elastic & Resizable Layout:** Fully resizable window utilizing responsive Qt containers (`QSplitter`, `QBoxLayout`, stretch factors) adapting smoothly to any screen resolution.
- **File Picker & Drag-and-Drop:** Drag and drop files directly onto the interactive drop zone or select via system file dialog.
- **Dual Size Control (Slider + Precise Input):**
  - **Dynamic Size Slider:** Ranging smoothly from maximum (original file size) down to a minimum of **1 Byte (1 B)**. Automatically synchronizes in real time.
  - **Numeric Spinbox & Unit Selector:** Supports **MB**, **KB**, and **B** units down to **1 Byte** for precise dimensions (e.g. `14.85 MB`, `500 KB`, or `1 B`) that cannot be touched easily with the slider.
  - **Percentage & Ratio Indicator:** Live feedback displaying target size and percentage of original file.
- **Quick Presets:** One-click presets for common limits: `8 MB (Discord)`, `15 MB`, `25 MB (Email)`, `50 MB`, `100 MB`.
- **Mode Selection:**
  - `Balanced`: Optimizes resolution and bitrate/quality to prevent macroblocking and visual compression artifacts.
  - `Preserve resolution`: Retains 100% of the original width and height, reducing only quality/bitrate.
  - `Scale resolution priority`: Prioritizes downscaling resolution to keep high bit density per pixel and crisp details.
- **Video FPS Limiter:**
  - Configurable maximum framerate (`No limit (Original)`, `60 FPS`, `50 FPS`, `30 FPS`, `25 FPS`, `24 FPS`, `15 FPS`, or `Custom...`).
  - Caps high-framerate videos (e.g. 60 FPS -> 30 FPS) to allocate up to 2x more bitrate per individual frame, drastically boosting sharpness and clarity at tight target file sizes.
  - Automatically disabled when an image file is loaded and active for video files with live source FPS display.
- **Dedicated Activity Log (Log Channel / Console):**
  - Real-time auto-scrolling console output.
  - Color-coded event tags (`[INFO]`, `[SUCCESS]`, `[WARN]`, `[ERROR]`).
  - Timestamps `[HH:MM:SS]` on every line.
  - Dedicated buttons for `Copy log` (to clipboard) and `Clear log`.

### 2. Safe I/O & Background Processing
- **Zero Overwriting:** The original file is NEVER overwritten.
- **Automatic Unique Naming:** Automatically creates an output file with `_compressed` suffix (e.g. `name_compressed.mp4` or `name_compressed(1).mp4` if one exists).
- **Custom Export Destination:** Option to save alongside the source file or specify a custom destination directory.
- **Quick Access Actions:** Dedicated `Open Compressed File` button to immediately launch the output file in the system default media player/viewer, and `Open Folder` button to reveal and highlight the compressed file in the file explorer.
- **Asynchronous Execution:** Runs on a dedicated background thread (`QThread`), keeping the UI fluid and responsive throughout the compression.
- **Cancel Button & Shortcut:** Safely terminates any active FFmpeg processes and cleans up temporary files without leaving orphaned tasks.

### 3. Compression Algorithms & Target Size Calculations

#### For Images (JPG, PNG, WEBP, BMP):
1. **Preliminary Guard:** If the source file is already under the target size, the operation exits cleanly without re-encoding.
2. **Binary Search on `quality`:**
   - Evaluates optimal quality within the feasible range `[min_quality, 95]`.
   - Tests candidate sizes directly in memory (`io.BytesIO`) for maximum speed without disk wear.
3. **Progressive Lanczos Downscaling:**
   - If minimum allowable quality cannot achieve the target constraint, downscaling is applied:
     $$\text{ratio} = \sqrt{\frac{\text{Target Bytes}}{\text{Current Bytes}}} \times 0.92$$
   - Applies high-quality `Image.Resampling.LANCZOS` resampling and repeats binary search until disk size $\le$ target.
   - For lossless PNG, tries lossless compression optimization, adaptive 256-color palette quantization, and Lanczos downscaling.

#### For Videos (MP4, MKV, MOV, WEBM):
1. **Metadata Probe:** Extracts duration, resolution, framerate, and audio presence via FFmpeg.
2. **Target Bitrate Formula (2-Pass Encoding):**
   $$\text{Total Bitrate (kbps)} = \frac{\text{Target Bytes} \times 8}{\text{Duration (seconds)} \times 1000} \times \text{Safety Margin (0.95)}$$
   $$\text{Video Bitrate} = \text{Total Bitrate} - \text{Audio Bitrate}$$
3. **Dynamic Audio Budget:**
   - Adapts audio bitrate (128k, 96k, 64k, 48k, or 32k) to not exceed 35% of the total budget.
   - If the video has no audio track, 100% of the bitrate is allocated to video.
4. **Artifact Protection (Dynamic Downscaling):**
   - Calculates bits per pixel:
     $$\text{bpp} = \frac{\text{video\_bitrate} \times 1000}{\text{width} \times \text{height} \times \text{fps}}$$
   - If bpp falls below acceptable compression thresholds, FFmpeg automatically applies `-vf "scale=-2:height"` to optimal standard resolutions (1080p -> 720p -> 480p -> 360p -> 240p).
5. **Framerate Limiting (Optional Cap):**
   - When configured, applies FFmpeg `-vf "fps=fps=<max_fps>"` to cap high framerate inputs (e.g. 60 FPS -> 30 FPS).
   - Recalculates effective bits per pixel with fewer frames, preserving higher bit density and detail without over-compressing individual frames.
6. **2-Pass Encoding:**
   - Pass 1: Frame complexity analysis and log generation (`-pass 1 -preset medium -an -f null`).
   - Pass 2: Final video compression and audio multiplexing (`-pass 2 -preset medium`).
   - Real-time progress monitoring parsed directly from FFmpeg stderr (`time=...`).

---

## Project Structure

```
wzresizer/
├── fonts/                     # Bundled Ubuntu TTF fonts
│   ├── Ubuntu-Regular.ttf
│   ├── Ubuntu-Medium.ttf
│   └── Ubuntu-Bold.ttf
├── core/
│   ├── __init__.py
│   ├── probe.py               # Media metadata probing (Pillow & FFmpeg)
│   ├── image_compressor.py    # Binary search quality + Lanczos downscaling
│   ├── video_compressor.py    # 2-Pass FFmpeg encoder + bitrate math
│   └── worker.py              # QThread background worker with UI signals
├── ui/
│   ├── __init__.py
│   ├── styles.py              # Clean utilitarian Dark Theme
│   ├── drop_area.py           # Drag-and-Drop zone & media specs viewer
│   ├── log_widget.py          # Activity log console with auto-scroll and copy
│   └── main_window.py         # Responsive main window with slider and controls
├── tests/
│   └── test_compressors.py    # Unit and integration test suite
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
└── run.bat                    # Windows quick-launch script
```

---

## Installation & Running

### 1. Requirements
Ensure Python 3.10+ is installed.

### 2. Install Dependencies
Run in your terminal or PowerShell:
```bash
pip install -r requirements.txt
```
*Note: The `imageio-ffmpeg` package automatically bundles official FFmpeg binaries, so no manual system PATH configuration is required.*

### 3. Run the Application
```bash
python main.py
```
or double-click `run.bat` on Windows.

### 4. Run Automated Tests
To validate probe extraction, image binary search, video 2-pass encoding, and output safeguards:
```bash
python -m unittest discover -s tests
```

---

## License & Notes
Developed with a strict focus on utility, performance, and deterministic output size.
