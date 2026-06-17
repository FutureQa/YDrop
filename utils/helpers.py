"""
YDrop — Utility helpers.

Thumbnail loading, duration formatting, URL validation,
icon generation, and Windows theme detection.
"""

import re
import struct
import sys
import threading
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"^https?://\S+", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    """Return True if url starts with http:// or https://."""
    return bool(_URL_RE.match(url.strip()))


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------

def format_duration(seconds: Optional[int]) -> str:
    """Format seconds into H:MM:SS or M:SS string."""
    if not seconds or seconds <= 0:
        return ""
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


# ---------------------------------------------------------------------------
# Thumbnail loading (background thread)
# ---------------------------------------------------------------------------

def load_thumbnail(
    url: str,
    size: tuple[int, int],
    callback: Callable[[Optional[Image.Image]], None],
) -> None:
    """
    Download and resize thumbnail in a background thread.

    callback receives a PIL Image on success, None on failure.
    """
    def _worker() -> None:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img = img.resize(size, Image.LANCZOS)
            callback(img)
        except Exception:
            callback(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Windows theme detection
# ---------------------------------------------------------------------------

def detect_windows_theme() -> str:
    """
    Read Windows registry to determine if system is using dark or light theme.

    Returns 'dark' or 'light'. Defaults to 'dark' if registry read fails.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

def generate_icon(output_path: Path) -> None:
    """
    Generate a simple YDrop icon programmatically using Pillow.

    Creates a 256x256 icon with a downward arrow on a gradient background.
    Saves as .ico format.
    """
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()

    # Gradient circle background
    cx, cy = size // 2, size // 2
    radius = size // 2 - 8
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                t = y / size
                r = int(99 + (139 - 99) * t)
                g = int(102 + (92 - 102) * t)
                b = int(241 + (246 - 241) * t)
                # Anti-alias the edge
                if dist > radius - 2:
                    alpha = int(255 * (radius - dist) / 2)
                    alpha = max(0, min(255, alpha))
                else:
                    alpha = 255
                pixels[x, y] = (r, g, b, alpha)

    # Draw a downward arrow (white)
    arrow_color = (255, 255, 255, 255)
    # Shaft
    shaft_width = 28
    shaft_top = 55
    shaft_bottom = 155
    for y in range(shaft_top, shaft_bottom):
        for x in range(cx - shaft_width // 2, cx + shaft_width // 2):
            pixels[x, y] = arrow_color

    # Arrowhead triangle
    head_top = 140
    head_bottom = 200
    head_half_width = 65
    for y in range(head_top, head_bottom):
        t = (y - head_top) / (head_bottom - head_top)
        w = int(head_half_width * (1 - t))
        for x in range(cx - w, cx + w):
            if 0 <= x < size:
                pixels[x, y] = arrow_color

    # Tray/line at bottom
    line_y_start = 205
    line_y_end = 215
    line_half = 70
    for y in range(line_y_start, line_y_end):
        for x in range(cx - line_half, cx + line_half):
            pixels[x, y] = arrow_color

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format="ICO", sizes=[(256, 256)])


def ensure_icon(assets_dir: Path) -> Path:
    """Ensure icon.ico exists; generate if missing. Returns icon path."""
    icon_path = assets_dir / "icon.ico"
    if not icon_path.exists():
        generate_icon(icon_path)
    return icon_path
