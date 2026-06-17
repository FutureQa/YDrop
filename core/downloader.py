"""
YDrop — Download engine.

Uses yt_dlp.YoutubeDL Python API with progress_hooks.
Manages a threaded queue with configurable concurrency via Semaphore.
"""

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import logging

import yt_dlp

from core import ffmpeg_manager


class _SilentLogger:
    """Drop all yt-dlp log output so it doesn't leak to stderr/console."""
    def debug(self, msg: str) -> None: pass
    def info(self, msg: str) -> None: pass
    def warning(self, msg: str) -> None: pass
    def error(self, msg: str) -> None: pass

# ---------------------------------------------------------------------------
# Format mapping
# ---------------------------------------------------------------------------

# Prefer h264 (avc1) over AV1 — AV1 streams fail to merge with many
# FFmpeg builds ("could not find codec parameters"). Fall back to any
# codec so the download still works if only AV1 is available.
# No static format maps anymore, formats are generated dynamically from UI string

# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

ERROR_MAP: dict[str, str] = {
    "Private video":              "Video unavailable: private.",
    "Video unavailable":          "Video unavailable: deleted or removed.",
    "Sign in":                    "This video requires login. Add a cookies file in Settings.",
    "No space left":              "Not enough disk space. Free up space and retry.",
    "Unable to download":         "No internet connection. Check your network.",
    "Requested format":           "Requested quality not available. Try a lower quality.",
    "is not a valid URL":         "This site is not supported by yt-dlp.",
    "Unsupported URL":            "This site is not supported by yt-dlp.",
    "Postprocessing":             "FFmpeg merge failed. Try installing latest FFmpeg in Settings.",
    "codec parameters":           "FFmpeg can't process this video codec. Try a different quality.",
    "Merging":                    "FFmpeg merge failed. Try installing latest FFmpeg in Settings.",
}

_DEFAULT_ERROR = "Download failed. Check the URL and try again."


def _map_error(msg: str) -> str:
    """Map a yt-dlp exception message to a user-friendly string."""
    for key, friendly in ERROR_MAP.items():
        if key.lower() in msg.lower():
            return friendly
    return _DEFAULT_ERROR


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DownloadItem:
    """Represents a single download in the queue."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    title: str = "Untitled"
    format_type: str = "video"          # 'video', 'audio', 'custom'
    format_key: str = "video_best"      # key into FORMAT_MAP or raw string
    output_folder: str = ""
    thumbnail_url: str = ""
    duration: int = 0                   # seconds
    status: str = "queued"              # queued|fetching|downloading|processing|done|error|cancelled
    progress: float = 0.0              # 0.0–1.0
    speed: str = ""
    eta: str = ""
    error_message: str = ""
    output_path: str = ""
    cookies_file: str = ""
    output_template: str = "%(title)s.%(ext)s"


# ---------------------------------------------------------------------------
# Info fetching (standalone, no queue needed)
# ---------------------------------------------------------------------------

def fetch_info(url: str, cookies_file: str = "") -> dict[str, Any]:
    """
    Fetch video/playlist metadata without downloading.

    Returns the yt-dlp info dict. Raises on failure.
    """
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    ffmpeg = ffmpeg_manager.get_ffmpeg_path()
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


# ---------------------------------------------------------------------------
# Download queue
# ---------------------------------------------------------------------------

class DownloadQueue:
    """
    Thread-safe download queue with concurrency control.

    UI callback signature: callback(item_id: str, item: DownloadItem)
    """

    def __init__(self, max_concurrent: int = 3) -> None:
        self._items: dict[str, DownloadItem] = {}
        self._order: list[str] = []            # insertion order
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._on_update: Optional[Callable[[str, DownloadItem], None]] = None
        self._cancel_flags: dict[str, threading.Event] = {}

    # -- callback -----------------------------------------------------------

    def set_update_callback(self, callback: Callable[[str, DownloadItem], None]) -> None:
        self._on_update = callback

    # -- public api ---------------------------------------------------------

    def add(self, item: DownloadItem) -> str:
        """Add item to queue and start download thread. Returns item id."""
        with self._lock:
            self._items[item.id] = item
            self._order.append(item.id)
            self._cancel_flags[item.id] = threading.Event()

        self._notify(item.id)
        t = threading.Thread(target=self._run_download, args=(item,), daemon=True)
        t.start()
        return item.id

    def cancel(self, item_id: str) -> None:
        """Signal cancellation for a running download."""
        flag = self._cancel_flags.get(item_id)
        if flag:
            flag.set()
        self._update_item(item_id, status="cancelled")

    def retry(self, item_id: str) -> None:
        """Retry a failed or cancelled download."""
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return
            item.status = "queued"
            item.progress = 0.0
            item.speed = ""
            item.eta = ""
            item.error_message = ""
            item.output_path = ""
            self._cancel_flags[item_id] = threading.Event()

        self._notify(item_id)
        t = threading.Thread(target=self._run_download, args=(item,), daemon=True)
        t.start()

    def remove(self, item_id: str) -> None:
        """Remove item from queue."""
        self.cancel(item_id)  # safety
        with self._lock:
            self._items.pop(item_id, None)
            if item_id in self._order:
                self._order.remove(item_id)
            self._cancel_flags.pop(item_id, None)
        self._notify(item_id)

    def get_item(self, item_id: str) -> Optional[DownloadItem]:
        with self._lock:
            return self._items.get(item_id)

    def get_all_items(self) -> list[DownloadItem]:
        with self._lock:
            return [self._items[iid] for iid in self._order if iid in self._items]

    def update_max_concurrent(self, n: int) -> None:
        """Replace semaphore with new count (affects future downloads only)."""
        self._semaphore = threading.Semaphore(n)
        self._max_concurrent = n

    # -- stats --------------------------------------------------------------

    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for it in self._items.values()
                if it.status in ("fetching", "downloading", "processing")
            )

    def done_count(self) -> int:
        with self._lock:
            return sum(1 for it in self._items.values() if it.status == "done")

    # -- internal -----------------------------------------------------------

    def _run_download(self, item: DownloadItem) -> None:
        """Execute download in a worker thread (blocks on semaphore)."""
        self._semaphore.acquire()
        try:
            self._do_download(item)
        finally:
            self._semaphore.release()

    def _do_download(self, item: DownloadItem) -> None:
        """Core download logic using yt_dlp.YoutubeDL."""
        cancel = self._cancel_flags.get(item.id)
        if cancel and cancel.is_set():
            return

        self._update_item(item.id, status="downloading", progress=0.0)

        # Build yt-dlp options
        output_template = str(Path(item.output_folder) / "%(title)s.%(ext)s")

        base_opts: dict[str, Any] = {
            "outtmpl": str(Path(item.output_folder) / item.output_template),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "no_color": True,
            "progress_hooks": [lambda d: self._progress_hook(item.id, d)],
            "postprocessor_hooks": [lambda d: self._pp_hook(item.id, d)],
            # Suppress yt-dlp's own logger to avoid ERROR lines on stderr
            "logger": _SilentLogger(),
        }

        # Cookies
        if item.cookies_file:
            base_opts["cookiefile"] = item.cookies_file

        # FFmpeg
        ffmpeg = ffmpeg_manager.get_ffmpeg_path()
        if ffmpeg:
            base_opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
        elif item.format_type == "audio":
            self._update_item(
                item.id,
                status="error",
                error_message="FFmpeg required for this format. Install it in Settings.",
            )
            return

        # Generate Fallbacks
        fallbacks: list[dict[str, Any]] = []

        if item.format_type == "custom":
            fallbacks.append({"format": item.format_key})

        elif item.format_type == "video":
            parts = item.format_key.split("|")
            q_str = parts[1] if len(parts) > 1 else "Best Quality"
            container = parts[2].lower() if len(parts) > 2 else "mp4"
            vcodec = parts[3] if len(parts) > 3 else ""

            hf = "" if q_str == "Best Quality" else f"[height<={q_str[:-1]}]" if q_str.endswith("p") else "[height<=2160]" if q_str == "4K" else f"[height<={q_str}]"
            
            # Fallback 1: Requested codec + container
            if vcodec:
                vf = f"[vcodec^={vcodec}]"
                fallbacks.append({
                    "format": f"bestvideo{hf}{vf}+bestaudio[acodec^=mp4a]/bestvideo{hf}{vf}+bestaudio/bestvideo{hf}+bestaudio",
                    "merge_output_format": container,
                })
            
            # Fallback 2: H.264 + container (Most compatible, safest for MP4)
            if vcodec != "avc1":
                fallbacks.append({
                    "format": f"bestvideo{hf}[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo{hf}[vcodec^=avc1]+bestaudio",
                    "merge_output_format": container,
                })
            
            # Fallback 3: Any codec + container (If avc1 wasn't requested natively)
            if vcodec:
                fallbacks.append({
                    "format": f"bestvideo{hf}+bestaudio[acodec^=mp4a]/bestvideo{hf}+bestaudio",
                    "merge_output_format": container,
                })
            
            # Fallback 4: Any codec + MKV (MKV swallows all, ignores container preference if it fails)
            if container != "mkv":
                fallbacks.append({
                    "format": f"bestvideo{hf}+bestaudio/best{hf}",
                    "merge_output_format": "mkv",
                })
                
            # Fallback 5: Single file fallback (No merge required)
            fallbacks.append({
                "format": f"best{hf}/best",
            })

        elif item.format_type == "audio":
            parts = item.format_key.split("|")
            fmt = parts[1].lower() if len(parts) > 1 else "mp3"
            q_str = parts[2] if len(parts) > 2 else "320k"
            quality = "0" if q_str == "Best Quality" else q_str[:-1] if q_str.endswith("k") else q_str
            
            # If fmt == 'ogg', yt-dlp FFmpegExtractAudio wants 'vorbis' or 'opus'
            pp_fmt = "vorbis" if fmt == "ogg" else fmt

            # Fallback 1: Requested format + quality
            fallbacks.append({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": pp_fmt,
                    "preferredquality": quality,
                }]
            })
            
            # Fallback 2: Requested format + best quality (0)
            if quality != "0":
                fallbacks.append({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": pp_fmt,
                        "preferredquality": "0",
                    }]
                })
            
            # Fallback 3: Native audio (no transcode)
            fallbacks.append({
                "format": "bestaudio/best",
            })

        # Retry Loop
        last_err = None
        for idx, fb in enumerate(fallbacks):
            if cancel and cancel.is_set():
                self._update_item(item.id, status="cancelled")
                return
                
            if idx > 0:
                self._update_item(item.id, status=f"retrying ({idx}/{len(fallbacks)-1})", progress=0.0, speed="", eta="")
                
            opts = dict(base_opts)
            opts.update(fb)
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([item.url])
                    
                if cancel and cancel.is_set():
                    self._update_item(item.id, status="cancelled")
                    return
                    
                self._update_item(item.id, status="done", progress=1.0, speed="", eta="")
                return # Success!
                
            except yt_dlp.utils.DownloadError as exc:
                last_err = exc
            except Exception as exc:
                last_err = exc
                
        # If we exhausted fallbacks
        if cancel and cancel.is_set():
            self._update_item(item.id, status="cancelled")
        elif last_err:
            friendly = _map_error(str(last_err))
            self._update_item(item.id, status="error", error_message=friendly)
        else:
            self._update_item(item.id, status="error", error_message=_DEFAULT_ERROR)

    def _progress_hook(self, item_id: str, data: dict[str, Any]) -> None:
        """yt-dlp progress_hook callback — runs in download thread."""
        cancel = self._cancel_flags.get(item_id)
        if cancel and cancel.is_set():
            raise yt_dlp.utils.DownloadError("Cancelled by user")

        status = data.get("status", "")
        updates: dict[str, Any] = {}

        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes", 0)
            if total > 0:
                updates["progress"] = downloaded / total
            speed = data.get("speed")
            if speed and speed > 0:
                if speed >= 1024 * 1024:
                    updates["speed"] = f"{speed / (1024 * 1024):.1f} MB/s"
                else:
                    updates["speed"] = f"{speed / 1024:.0f} KB/s"
            eta = data.get("eta")
            if eta is not None:
                mins, secs = divmod(int(eta), 60)
                hours, mins = divmod(mins, 60)
                if hours:
                    updates["eta"] = f"{hours}:{mins:02d}:{secs:02d}"
                else:
                    updates["eta"] = f"{mins}:{secs:02d}"
            updates["status"] = "downloading"

        elif status == "finished":
            filepath = data.get("filename", "")
            updates["output_path"] = filepath
            updates["status"] = "processing"
            updates["progress"] = 1.0
            updates["speed"] = ""
            updates["eta"] = ""

        if updates:
            self._update_item(item_id, **updates)

    def _pp_hook(self, item_id: str, data: dict[str, Any]) -> None:
        """Postprocessor hook — track final output path."""
        status = data.get("status", "")
        if status == "finished":
            filepath = data.get("filename", "")
            if filepath:
                self._update_item(item_id, output_path=filepath)

    def _update_item(self, item_id: str, **kwargs: Any) -> None:
        """Thread-safe update of item fields + notify UI."""
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return
            for k, v in kwargs.items():
                if hasattr(item, k):
                    setattr(item, k, v)
        self._notify(item_id)

    def _notify(self, item_id: str) -> None:
        """Fire UI callback if registered."""
        if self._on_update:
            with self._lock:
                item = self._items.get(item_id)
            if item:
                self._on_update(item_id, item)
