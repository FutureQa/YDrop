"""
YDrop — FFmpeg detection and auto-download.

1. Check PATH via shutil.which
2. Check AppData/Local/YDrop/ffmpeg/ffmpeg.exe
3. If neither, download portable FFmpeg in a background thread
"""

import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FFMPEG_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YDrop" / "ffmpeg"
_FFMPEG_EXE = _FFMPEG_DIR / "ffmpeg.exe"
_DOWNLOAD_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)

# Type alias for progress callback: (status_text, percent 0-100 or -1)
ProgressCallback = Callable[[str, int], None]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_ffmpeg_path() -> Optional[str]:
    """Return absolute path to ffmpeg if available, None otherwise."""
    # 1. System PATH
    system = shutil.which("ffmpeg")
    if system:
        return str(Path(system).resolve())

    # 2. Local AppData copy
    if _FFMPEG_EXE.is_file():
        return str(_FFMPEG_EXE)

    return None


def get_ffmpeg_status() -> str:
    """Return a human-readable status string for the settings panel."""
    path = get_ffmpeg_path()
    if path:
        return f"✓ Found at: {path}"
    return "✗ Not found"


def download_ffmpeg(callback: Optional[ProgressCallback] = None) -> Optional[str]:
    """
    Download portable FFmpeg and extract ffmpeg.exe to AppData.

    Blocks until complete — intended to run in a background thread.
    Returns the path string on success, None on failure.
    """
    def _report(text: str, pct: int) -> None:
        if callback:
            callback(text, pct)

    try:
        _report("Connecting to GitHub…", 0)
        resp = requests.get(_DOWNLOAD_URL, stream=True, timeout=60)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunks: list[bytes] = []

        for chunk in resp.iter_content(chunk_size=1024 * 256):
            chunks.append(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int(downloaded / total * 100)
                mb = downloaded / (1024 * 1024)
                _report(f"Downloading… {mb:.1f} MB", pct)
            else:
                _report("Downloading…", -1)

        _report("Extracting ffmpeg.exe…", 95)
        data = b"".join(chunks)
        _FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(BytesIO(data)) as zf:
            # Find ffmpeg.exe inside the archive (may be nested in a subdir)
            target_names = [
                n for n in zf.namelist()
                if n.lower().endswith("ffmpeg.exe") and "ffprobe" not in n.lower()
            ]
            if not target_names:
                _report("Error: ffmpeg.exe not found in archive.", -1)
                return None

            # Extract into our ffmpeg dir
            src = target_names[0]
            with zf.open(src) as src_fh, open(_FFMPEG_EXE, "wb") as dst_fh:
                shutil.copyfileobj(src_fh, dst_fh)

            # Also extract ffprobe if present (yt-dlp uses it)
            ffprobe_names = [
                n for n in zf.namelist()
                if n.lower().endswith("ffprobe.exe")
            ]
            if ffprobe_names:
                ffprobe_path = _FFMPEG_DIR / "ffprobe.exe"
                with zf.open(ffprobe_names[0]) as src_fh, open(ffprobe_path, "wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)

        _report("✓ FFmpeg installed.", 100)
        return str(_FFMPEG_EXE)

    except requests.RequestException as exc:
        _report(f"Download failed: {exc}", -1)
        return None
    except (zipfile.BadZipFile, OSError) as exc:
        _report(f"Extraction failed: {exc}", -1)
        return None
