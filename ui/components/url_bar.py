"""
YDrop — URL input bar component.

Handles URL entry, clipboard paste, info fetching, and metadata display.
"""

import threading
import customtkinter as ctk
from typing import Callable, Optional, Any

from utils.helpers import is_valid_url, format_duration

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LBL_URL_PLACEHOLDER = "Paste a video or playlist URL…"
LBL_PASTE = "Paste"
LBL_FETCH = "Fetch ▶"
LBL_FETCHING = "Fetching…"
LBL_ERROR_INVALID = "Enter a valid URL starting with http:// or https://"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

CLR_ERROR = "#FF4C6A"
CLR_SUCCESS = "#4AE08C"
CLR_MUTED = "#8B8FA3"
CLR_ACCENT = "#6366F1"
CLR_ACCENT_HOVER = "#818CF8"


class URLBar(ctk.CTkFrame):
    """
    Top URL input area with paste button, fetch button, and info display.

    on_info_fetched callback: (info_dict) -> None
    """

    def __init__(
        self,
        master: Any,
        fetch_fn: Callable[[str], dict],
        on_info_fetched: Callable[[dict], None],
        cookies_file_fn: Callable[[], str],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._fetch_fn = fetch_fn
        self._on_info_fetched = on_info_fetched
        self._cookies_file_fn = cookies_file_fn
        self._fetching = False

        # -- row 0: url input + buttons ------------------------------------
        self.grid_columnconfigure(1, weight=1)

        self._url_var = ctk.StringVar()
        self._url_entry = ctk.CTkEntry(
            self,
            textvariable=self._url_var,
            placeholder_text=LBL_URL_PLACEHOLDER,
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
        )
        self._url_entry.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8))
        self._url_entry.bind("<Return>", lambda e: self._on_fetch())

        self._paste_btn = ctk.CTkButton(
            self,
            text=LBL_PASTE,
            width=70,
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._on_paste,
        )
        self._paste_btn.grid(row=0, column=2, padx=(0, 6))

        self._fetch_btn = ctk.CTkButton(
            self,
            text=LBL_FETCH,
            width=100,
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
            command=self._on_fetch,
        )
        self._fetch_btn.grid(row=0, column=3)

        # -- row 1: info / error label -------------------------------------
        self._info_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=13),
            text_color=CLR_MUTED,
        )
        self._info_label.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))

    # -- public api ---------------------------------------------------------

    def get_url(self) -> str:
        return self._url_var.get().strip()

    def set_url(self, url: str) -> None:
        self._url_var.set(url)

    def get_last_info(self) -> Optional[dict]:
        return getattr(self, "_last_info", None)

    # -- handlers -----------------------------------------------------------

    def _on_paste(self) -> None:
        """Read clipboard and paste into URL field."""
        try:
            text = self.clipboard_get()
            if text:
                self._url_var.set(text.strip())
                self._info_label.configure(text="", text_color=CLR_MUTED)
        except Exception:
            pass

    def _on_fetch(self) -> None:
        """Validate URL and start background info fetch."""
        if self._fetching:
            return

        url = self.get_url()
        if not is_valid_url(url):
            self._info_label.configure(text=LBL_ERROR_INVALID, text_color=CLR_ERROR)
            return

        self._fetching = True
        self._fetch_btn.configure(text=LBL_FETCHING, state="disabled")
        self._info_label.configure(text="Fetching video info…", text_color=CLR_MUTED)

        t = threading.Thread(target=self._fetch_worker, args=(url,), daemon=True)
        t.start()

    def _fetch_worker(self, url: str) -> None:
        """Background thread: fetch info from yt-dlp."""
        try:
            cookies = self._cookies_file_fn()
            from core.downloader import fetch_info
            info = fetch_info(url, cookies)
            self._last_info = info

            # Build display text
            title = info.get("title", "Unknown")
            duration = info.get("duration")
            is_playlist = info.get("_type") == "playlist"

            if is_playlist:
                entries = info.get("entries", [])
                count = len(list(entries)) if entries else 0
                text = f"📋 Playlist: {title} · {count} videos"
            else:
                dur_str = format_duration(duration)
                text = f"{title}"
                if dur_str:
                    text += f" · {dur_str}"

            self.after(0, lambda: self._on_fetch_success(text, info))

        except Exception as exc:
            msg = str(exc)
            # Extract user-friendly message
            from core.downloader import _map_error
            friendly = _map_error(msg)
            self.after(0, lambda: self._on_fetch_error(friendly))

    def _on_fetch_success(self, display_text: str, info: dict) -> None:
        """UI thread: show fetched info."""
        self._fetching = False
        self._fetch_btn.configure(text=LBL_FETCH, state="normal")
        self._info_label.configure(text=display_text, text_color=CLR_SUCCESS)
        self._on_info_fetched(info)

    def _on_fetch_error(self, message: str) -> None:
        """UI thread: show error."""
        self._fetching = False
        self._fetch_btn.configure(text=LBL_FETCH, state="normal")
        self._info_label.configure(text=message, text_color=CLR_ERROR)
