"""
YDrop — Main application window.

Assembles URL bar, format panel, queue view, and settings button into
the primary CustomTkinter window. Handles playlist dialogs and wires
all components to the download engine.
"""

import customtkinter as ctk
from pathlib import Path
from typing import Any, Optional

from version import APP_VERSION, APP_NAME
from core.settings import Settings
from core.downloader import DownloadItem, DownloadQueue
from core import ffmpeg_manager
from utils.helpers import detect_windows_theme, ensure_icon
from ui.components.url_bar import URLBar
from ui.components.format_panel import FormatPanel
from ui.components.queue_view import QueueView
from ui.components.settings_window import SettingsWindow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"
MIN_WIDTH = 720
MIN_HEIGHT = 520
DEFAULT_WIDTH = 860
DEFAULT_HEIGHT = 640

CLR_ACCENT = "#6366F1"
CLR_ACCENT_HOVER = "#818CF8"
CLR_HEADER_BG = "#111827"
CLR_HEADER_BG_LIGHT = "#E2E8F0"


class YDropApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        # -- settings -------------------------------------------------------
        self._settings = Settings()
        self._apply_theme(self._settings.get("theme"))

        # -- window setup ---------------------------------------------------
        self.title(WINDOW_TITLE)
        self.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        # Icon
        icon_path = ensure_icon(Path(__file__).resolve().parent.parent / "assets")
        try:
            self.iconbitmap(str(icon_path))
        except Exception:
            pass

        # -- download queue -------------------------------------------------
        max_concurrent = self._settings.get("max_concurrent")
        self._queue = DownloadQueue(max_concurrent=max_concurrent)

        # -- track last fetched info ----------------------------------------
        self._last_info: Optional[dict] = None

        # -- layout ---------------------------------------------------------
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # queue view expands

        self._build_header()
        self._build_url_bar()
        self._build_format_panel()
        self._build_queue_view()

    # -- builders -----------------------------------------------------------

    def _build_header(self) -> None:
        """Top bar with app name and settings gear."""
        header = ctk.CTkFrame(self, height=44, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text=f"  {WINDOW_TITLE}",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        settings_btn = ctk.CTkButton(
            header,
            text="⚙",
            width=36,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=18),
            fg_color="transparent",
            hover_color="#374151",
            command=self._open_settings,
        )
        settings_btn.grid(row=0, column=1, padx=8, pady=6)

    def _build_url_bar(self) -> None:
        self._url_bar = URLBar(
            self,
            fetch_fn=lambda url: {},  # not used directly
            on_info_fetched=self._on_info_fetched,
            cookies_file_fn=lambda: self._settings.get("cookies_file"),
        )
        self._url_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 8))

    def _build_format_panel(self) -> None:
        # Resolve initial format from settings
        default_fmt = self._settings.get("default_format")
        if default_fmt == "remember":
            fmt_type = self._settings.get("last_format_type")
            video_q = self._settings.get("last_video_quality")
            video_c = self._settings.get("last_video_format")
            video_vcodec = self._settings.get("last_video_codec")
            audio_f = self._settings.get("last_audio_format")
            audio_q = self._settings.get("last_audio_quality")
        else:
            fmt_type = "video"
            video_q = "Best Quality"
            video_c = "MP4"
            video_vcodec = "Any Codec"
            audio_f = "MP3"
            audio_q = "320k"

        self._format_panel = FormatPanel(
            self,
            initial_format_type=fmt_type,
            initial_video_q=video_q,
            initial_video_c=video_c,
            initial_video_vcodec=video_vcodec,
            initial_audio_f=audio_f,
            initial_audio_q=audio_q,
            on_add_to_queue=self._on_add_to_queue,
            on_format_change=self._on_format_change,
        )
        self._format_panel.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

    def _build_queue_view(self) -> None:
        self._queue_view = QueueView(self, queue=self._queue)
        self._queue_view.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))

    # -- event handlers -----------------------------------------------------

    def _on_info_fetched(self, info: dict) -> None:
        """Called when URL bar successfully fetches video info."""
        self._last_info = info

        is_playlist = info.get("_type") == "playlist"
        if is_playlist:
            self._show_playlist_dialog(info)

    def _on_add_to_queue(self) -> None:
        """Add current URL + format to download queue."""
        info = self._last_info
        url = self._url_bar.get_url()

        if not url:
            return

        # If info was fetched, use it; otherwise create a basic item
        if info and info.get("_type") != "playlist":
            self._enqueue_single(info, url)
        elif not info:
            # No fetch done — create item with URL only, title will be "Untitled"
            self._enqueue_single({}, url)

    def _enqueue_single(self, info: dict, url: str) -> None:
        """Create and enqueue a single download item."""
        fmt_type = self._format_panel.get_format_type()
        fmt_key = self._format_panel.get_format_key()
        fmt_display = self._format_panel.get_format_display()
        # Create the item
        folder = self._settings.get("output_folder")
        item = DownloadItem(
            url=url,
            title=info.get("title", "Untitled"),
            format_type=fmt_type,
            format_key=fmt_key,
            output_folder=folder,
            thumbnail_url=info.get("thumbnail", ""),
            duration=info.get("duration", 0),
            cookies_file=self._settings.get("cookies_file"),
        )

        self._queue_view.set_format_display(item.id, fmt_display)
        self._queue.add(item)

        # Save preferences if remembering
        if self._settings.get("default_format") == "remember":
            state = self._format_panel.get_state()
            self._settings.set("last_format_type", state["format_type"])
            self._settings.set("last_video_quality", state["video_q"])
            self._settings.set("last_video_format", state["video_c"])
            self._settings.set("last_video_codec", state["video_vcodec"])
            self._settings.set("last_audio_format", state["audio_f"])
            self._settings.set("last_audio_quality", state["audio_q"])

    def _on_format_change(self, fmt_type: str, fmt_key: str) -> None:
        """Track format changes for 'remember' mode."""
        pass  # Saved on add-to-queue

    # -- playlist dialog ----------------------------------------------------

    def _show_playlist_dialog(self, info: dict) -> None:
        """Show dialog asking whether to download entire playlist or first video."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Playlist Detected")
        dialog.geometry("420x160")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 420) // 2
        y = self.winfo_y() + (self.winfo_height() - 160) // 2
        dialog.geometry(f"+{x}+{y}")

        entries = info.get("entries", [])
        entry_list = list(entries) if entries else []
        count = len(entry_list)

        label = ctk.CTkLabel(
            dialog,
            text=f"This URL is a playlist with {count} videos.\nWhat would you like to do?",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        label.pack(pady=(20, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def _download_all() -> None:
            dialog.grab_release()
            dialog.destroy()
            self._enqueue_playlist(entry_list, info)

        def _first_only() -> None:
            dialog.grab_release()
            dialog.destroy()
            if entry_list:
                first = entry_list[0]
                first_url = first.get("url") or first.get("webpage_url", self._url_bar.get_url())
                self._enqueue_single(first, first_url)

        all_btn = ctk.CTkButton(
            btn_frame,
            text="Download All",
            width=140,
            height=38,
            corner_radius=10,
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=_download_all,
        )
        all_btn.pack(side="left", padx=(0, 12))

        first_btn = ctk.CTkButton(
            btn_frame,
            text="First Video Only",
            width=140,
            height=38,
            corner_radius=10,
            fg_color="#374151",
            hover_color="#4B5563",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=_first_only,
        )
        first_btn.pack(side="left")

    def _enqueue_playlist(self, entries: list[dict], playlist_info: dict) -> None:
        """Add each playlist entry as a separate download card."""
        fmt_type = self._format_panel.get_format_type()
        fmt_key = self._format_panel.get_format_key()
        fmt_display = self._format_panel.get_format_display()
        folder = self._settings.get("output_folder")

        for entry in entries:
            url = entry.get("url") or entry.get("webpage_url", "")
            if not url:
                continue

            item = DownloadItem(
                url=url,
                title=entry.get("title", "Untitled"),
                format_type=fmt_type,
                format_key=fmt_key,
                output_folder=folder,
                thumbnail_url=entry.get("thumbnail", ""),
                duration=entry.get("duration", 0),
                cookies_file=self._settings.get("cookies_file"),
            )

            self._queue_view.set_format_display(item.id, fmt_display)
            self._queue.add(item)

    # -- settings -----------------------------------------------------------

    def _open_settings(self) -> None:
        SettingsWindow(
            self,
            settings=self._settings,
            on_theme_change=self._apply_theme,
            on_max_concurrent_change=self._queue.update_max_concurrent,
        )

    def _apply_theme(self, theme: str) -> None:
        """Apply theme setting, resolving 'system' via registry."""
        if theme == "system":
            resolved = detect_windows_theme()
        else:
            resolved = theme
        ctk.set_appearance_mode(resolved.capitalize())
