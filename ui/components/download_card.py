"""
YDrop — Download card component.

Displays a single download item with thumbnail, title, progress bar,
speed/ETA, and action buttons. All state updates go through configure_from_item().
"""

import os
import customtkinter as ctk
from PIL import Image
from typing import Any, Callable, Optional

from core.downloader import DownloadItem
from utils.helpers import load_thumbnail

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LBL_CANCEL = "Cancel"
LBL_RETRY = "Retry"
LBL_REMOVE = "✕"
LBL_OPEN_FOLDER = "📁 Open"
LBL_QUEUED = "Queued"
LBL_DOWNLOADING = "Downloading"
LBL_PROCESSING = "Processing…"
LBL_DONE = "✓ Done"
LBL_ERROR = "✗ Error"
LBL_CANCELLED = "Cancelled"
LBL_FETCHING = "Fetching…"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

CLR_CARD_BG = "#1C1C2E"
CLR_CARD_BG_LIGHT = "#FFFFFF"
CLR_SUCCESS = "#4AE08C"
CLR_ERROR = "#FF4C6A"
CLR_MUTED = "#8B8FA3"
CLR_ACCENT = "#6366F1"
CLR_ACCENT_HOVER = "#818CF8"
CLR_CANCEL = "#EF4444"
CLR_CANCEL_HOVER = "#F87171"
CLR_PROGRESS_BG = "#2D2D44"
CLR_PROGRESS_FG = "#6366F1"

THUMB_SIZE = (80, 45)


class DownloadCard(ctk.CTkFrame):
    """
    A card representing a single download in the queue.

    Actions are dispatched via callbacks:
      on_cancel(item_id), on_retry(item_id), on_remove(item_id), on_open_folder(path)
    """

    def __init__(
        self,
        master: Any,
        item: DownloadItem,
        on_cancel: Optional[Callable[[str], None]] = None,
        on_retry: Optional[Callable[[str], None]] = None,
        on_remove: Optional[Callable[[str], None]] = None,
        on_open_folder: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        self._item_id = item.id
        self._on_cancel = on_cancel
        self._on_retry = on_retry
        self._on_remove = on_remove
        self._on_open_folder = on_open_folder
        self._output_path = ""
        self._output_folder = item.output_folder

        self.grid_columnconfigure(1, weight=1)

        # -- thumbnail (left) ----------------------------------------------
        self._thumb_label = ctk.CTkLabel(
            self,
            text="",
            width=THUMB_SIZE[0],
            height=THUMB_SIZE[1],
            corner_radius=6,
            fg_color="#2D2D44",
        )
        self._thumb_label.grid(row=0, column=0, rowspan=3, padx=(12, 10), pady=12, sticky="nw")

        # Start thumbnail load
        if item.thumbnail_url:
            self._load_thumb(item.thumbnail_url)

        # -- title + action buttons (right top) ----------------------------
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 0))
        top_row.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            top_row,
            text=item.title,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._title_label.grid(row=0, column=0, sticky="w")

        # Status label
        self._status_label = ctk.CTkLabel(
            top_row,
            text="",
            anchor="e",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._status_label.grid(row=0, column=1, padx=(8, 0))

        # Action buttons container
        self._btn_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        self._btn_frame.grid(row=0, column=2, padx=(6, 0))

        self._cancel_btn = ctk.CTkButton(
            self._btn_frame, text=LBL_CANCEL, width=65, height=28,
            corner_radius=6, font=ctk.CTkFont(size=12),
            fg_color=CLR_CANCEL, hover_color=CLR_CANCEL_HOVER,
            command=self._handle_cancel,
        )
        self._retry_btn = ctk.CTkButton(
            self._btn_frame, text=LBL_RETRY, width=60, height=28,
            corner_radius=6, font=ctk.CTkFont(size=12),
            fg_color="#374151", hover_color="#4B5563",
            command=self._handle_retry,
        )
        self._open_btn = ctk.CTkButton(
            self._btn_frame, text=LBL_OPEN_FOLDER, width=68, height=28,
            corner_radius=6, font=ctk.CTkFont(size=12),
            fg_color="#374151", hover_color="#4B5563",
            command=self._handle_open,
        )
        self._remove_btn = ctk.CTkButton(
            self._btn_frame, text=LBL_REMOVE, width=32, height=28,
            corner_radius=6, font=ctk.CTkFont(size=14),
            fg_color="#374151", hover_color="#4B5563",
            command=self._handle_remove,
        )

        # -- info row (format, speed, ETA) ---------------------------------
        self._info_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=CLR_MUTED,
        )
        self._info_label.grid(row=1, column=1, sticky="ew", padx=(0, 12))

        # -- progress bar row ----------------------------------------------
        progress_row = ctk.CTkFrame(self, fg_color="transparent")
        progress_row.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(4, 12))
        progress_row.grid_columnconfigure(0, weight=1)

        self._progress_bar = ctk.CTkProgressBar(
            progress_row,
            height=8,
            corner_radius=4,
            progress_color=CLR_PROGRESS_FG,
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=0, sticky="ew")

        self._percent_label = ctk.CTkLabel(
            progress_row,
            text="",
            width=48,
            anchor="e",
            font=ctk.CTkFont(size=12),
            text_color=CLR_MUTED,
        )
        self._percent_label.grid(row=0, column=1, padx=(8, 0))

        # -- initial state --------------------------------------------------
        self._format_display = ""
        self.configure_from_item(item)

    # -- public api ---------------------------------------------------------

    def configure_from_item(self, item: DownloadItem) -> None:
        """Update all visual elements from a DownloadItem. Called from main thread."""
        self._item_id = item.id
        self._output_path = item.output_path
        self._output_folder = item.output_folder

        # Title
        self._title_label.configure(text=item.title)

        # Progress
        self._progress_bar.set(item.progress)
        pct = int(item.progress * 100)
        self._percent_label.configure(text=f"{pct}%" if pct > 0 else "")

        # Info line
        parts: list[str] = []
        if self._format_display:
            parts.append(self._format_display)
        if item.speed:
            parts.append(item.speed)
        if item.eta:
            parts.append(f"ETA {item.eta}")
        self._info_label.configure(text=" · ".join(parts))

        # Status label + button visibility
        self._show_buttons_for_status(item.status, item.error_message)

    def set_format_display(self, text: str) -> None:
        """Set the human-readable format label."""
        self._format_display = text

    @property
    def item_id(self) -> str:
        return self._item_id

    # -- internal -----------------------------------------------------------

    def _show_buttons_for_status(self, status: str, error_msg: str = "") -> None:
        """Show/hide buttons and status label based on download state."""
        # Clear all buttons
        for w in (self._cancel_btn, self._retry_btn, self._open_btn, self._remove_btn):
            w.pack_forget()

        if status in ("queued", "fetching", "downloading", "processing"):
            self._cancel_btn.pack(side="left", padx=(2, 0))
            if status == "queued":
                self._status_label.configure(text=LBL_QUEUED, text_color=CLR_MUTED)
            elif status == "fetching":
                self._status_label.configure(text=LBL_FETCHING, text_color=CLR_MUTED)
            elif status == "downloading":
                self._status_label.configure(text="", text_color=CLR_MUTED)
            elif status == "processing":
                self._status_label.configure(text=LBL_PROCESSING, text_color=CLR_ACCENT)

        elif status == "done":
            self._status_label.configure(text=LBL_DONE, text_color=CLR_SUCCESS)
            self._open_btn.pack(side="left", padx=(2, 0))
            self._remove_btn.pack(side="left", padx=(2, 0))
            self._progress_bar.configure(progress_color=CLR_SUCCESS)

        elif status == "error":
            self._status_label.configure(text=LBL_ERROR, text_color=CLR_ERROR)
            self._retry_btn.pack(side="left", padx=(2, 0))
            self._remove_btn.pack(side="left", padx=(2, 0))
            self._progress_bar.configure(progress_color=CLR_ERROR)
            # Show error in info line
            if error_msg:
                self._info_label.configure(text=error_msg, text_color=CLR_ERROR)

        elif status == "cancelled":
            self._status_label.configure(text=LBL_CANCELLED, text_color=CLR_MUTED)
            self._retry_btn.pack(side="left", padx=(2, 0))
            self._remove_btn.pack(side="left", padx=(2, 0))

    def _load_thumb(self, url: str) -> None:
        """Start background thumbnail download."""
        def _on_loaded(img: Optional[Image.Image]) -> None:
            if img:
                ctk_img = ctk.CTkImage(
                    light_image=img,
                    dark_image=img,
                    size=THUMB_SIZE,
                )
                self.after(0, lambda: self._thumb_label.configure(image=ctk_img, text=""))
                self._thumb_ctk_img = ctk_img  # prevent GC

        load_thumbnail(url, THUMB_SIZE, _on_loaded)

    # -- button handlers ----------------------------------------------------

    def _handle_cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel(self._item_id)

    def _handle_retry(self) -> None:
        if self._on_retry:
            self._on_retry(self._item_id)

    def _handle_remove(self) -> None:
        if self._on_remove:
            self._on_remove(self._item_id)

    def _handle_open(self) -> None:
        if not self._on_open_folder:
            return
        if self._output_path:
            folder = str(os.path.dirname(self._output_path))
        else:
            folder = self._output_folder
        if folder:
            self._on_open_folder(folder)
