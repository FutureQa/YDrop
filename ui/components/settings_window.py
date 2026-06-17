"""
YDrop — Settings window (modal dialog).

Contains: output folder, theme, default format, max concurrent downloads,
cookies file, yt-dlp update check, FFmpeg status.
"""

import subprocess
import sys
import threading
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable, Optional

from core.settings import Settings
from core import ffmpeg_manager

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LBL_TITLE = "Settings"
LBL_OUTPUT_FOLDER = "Output Folder"
LBL_THEME = "Theme"
LBL_DEFAULT_FORMAT = "Default Format"
LBL_MAX_CONCURRENT = "Max Simultaneous Downloads"
LBL_COOKIES = "Cookies File (optional)"
LBL_YTDLP_UPDATE = "Check for yt-dlp Updates"
LBL_FFMPEG_STATUS = "FFmpeg Status"
LBL_FFMPEG_DOWNLOAD = "Download FFmpeg"
LBL_CLOSE = "Close"

THEME_OPTIONS = ["Dark", "Light", "System"]
FORMAT_OPTIONS = {
    "Video (Best)": "video_best",
    "Audio (MP3)": "audio_mp3",
    "Remember Last": "remember",
}

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

CLR_ACCENT = "#6366F1"
CLR_ACCENT_HOVER = "#818CF8"
CLR_SUCCESS = "#4AE08C"
CLR_ERROR = "#FF4C6A"
CLR_MUTED = "#8B8FA3"


class SettingsWindow(ctk.CTkToplevel):
    """Modal settings dialog."""

    def __init__(
        self,
        master: Any,
        settings: Settings,
        on_theme_change: Callable[[str], None],
        on_max_concurrent_change: Callable[[int], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)

        self._settings = settings
        self._on_theme_change = on_theme_change
        self._on_max_concurrent_change = on_max_concurrent_change

        self.title(LBL_TITLE)
        self.geometry("520x620")
        self.resizable(False, False)
        self.transient(master)
        # No grab_set() — it breaks permanently when set_appearance_mode()
        # redraws widgets. Use focus + lift + protocol instead.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - 520) // 2
        y = master.winfo_y() + (master.winfo_height() - 620) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui()
        self.focus_force()
        self.lift()

    def _build_ui(self) -> None:
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.grid_columnconfigure(1, weight=1)
        row = 0

        # -- Title ----------------------------------------------------------
        title = ctk.CTkLabel(
            container,
            text=LBL_TITLE,
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        title.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 20))
        row += 1

        # -- Output Folder --------------------------------------------------
        self._section_label(container, LBL_OUTPUT_FOLDER, row)
        row += 1

        folder_frame = ctk.CTkFrame(container, fg_color="transparent")
        folder_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        folder_frame.grid_columnconfigure(0, weight=1)

        self._output_var = ctk.StringVar(value=self._settings.get("output_folder"))
        self._output_entry = ctk.CTkEntry(
            folder_frame,
            textvariable=self._output_var,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
        )
        self._output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        browse_btn = ctk.CTkButton(
            folder_frame,
            text="Browse",
            width=70,
            height=34,
            corner_radius=8,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._browse_output,
        )
        browse_btn.grid(row=0, column=1)
        row += 1

        # -- Theme ----------------------------------------------------------
        self._section_label(container, LBL_THEME, row)
        row += 1

        theme_val = self._settings.get("theme").capitalize()
        self._theme_var = ctk.StringVar(value=theme_val)

        theme_frame = ctk.CTkFrame(container, fg_color="transparent")
        theme_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        for i, opt in enumerate(THEME_OPTIONS):
            rb = ctk.CTkRadioButton(
                theme_frame,
                text=opt,
                variable=self._theme_var,
                value=opt,
                font=ctk.CTkFont(size=13),
                command=self._on_theme_selected,
                fg_color=CLR_ACCENT,
                hover_color=CLR_ACCENT_HOVER,
            )
            rb.grid(row=0, column=i, padx=(0, 16))
        row += 1

        # -- Default Format -------------------------------------------------
        self._section_label(container, LBL_DEFAULT_FORMAT, row)
        row += 1

        current_fmt = self._settings.get("default_format")
        current_fmt_label = next(
            (k for k, v in FORMAT_OPTIONS.items() if v == current_fmt),
            "Remember Last",
        )
        self._format_var = ctk.StringVar(value=current_fmt_label)

        fmt_frame = ctk.CTkFrame(container, fg_color="transparent")
        fmt_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        for i, opt in enumerate(FORMAT_OPTIONS.keys()):
            rb = ctk.CTkRadioButton(
                fmt_frame,
                text=opt,
                variable=self._format_var,
                value=opt,
                font=ctk.CTkFont(size=13),
                command=self._on_format_selected,
                fg_color=CLR_ACCENT,
                hover_color=CLR_ACCENT_HOVER,
            )
            rb.grid(row=0, column=i, padx=(0, 16))
        row += 1

        # -- Max Concurrent -------------------------------------------------
        self._section_label(container, LBL_MAX_CONCURRENT, row)
        row += 1

        slider_frame = ctk.CTkFrame(container, fg_color="transparent")
        slider_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        slider_frame.grid_columnconfigure(0, weight=1)

        self._concurrent_val = ctk.IntVar(value=self._settings.get("max_concurrent"))
        self._concurrent_label = ctk.CTkLabel(
            slider_frame,
            text=str(self._concurrent_val.get()),
            width=30,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._concurrent_label.grid(row=0, column=1, padx=(8, 0))

        self._concurrent_slider = ctk.CTkSlider(
            slider_frame,
            from_=1,
            to=5,
            number_of_steps=4,
            variable=self._concurrent_val,
            command=self._on_concurrent_changed,
            button_color=CLR_ACCENT,
            button_hover_color=CLR_ACCENT_HOVER,
            progress_color=CLR_ACCENT,
        )
        self._concurrent_slider.grid(row=0, column=0, sticky="ew")
        row += 1

        # -- Cookies File ---------------------------------------------------
        self._section_label(container, LBL_COOKIES, row)
        row += 1

        cookies_frame = ctk.CTkFrame(container, fg_color="transparent")
        cookies_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        cookies_frame.grid_columnconfigure(0, weight=1)

        self._cookies_var = ctk.StringVar(value=self._settings.get("cookies_file"))
        self._cookies_entry = ctk.CTkEntry(
            cookies_frame,
            textvariable=self._cookies_var,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            placeholder_text="Path to cookies.txt (optional)",
        )
        self._cookies_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        cookies_browse = ctk.CTkButton(
            cookies_frame,
            text="Browse",
            width=70,
            height=34,
            corner_radius=8,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._browse_cookies,
        )
        cookies_browse.grid(row=0, column=1)
        row += 1

        # -- yt-dlp Update --------------------------------------------------
        self._section_label(container, LBL_YTDLP_UPDATE, row)
        row += 1

        update_frame = ctk.CTkFrame(container, fg_color="transparent")
        update_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        update_frame.grid_columnconfigure(1, weight=1)

        self._update_btn = ctk.CTkButton(
            update_frame,
            text="Check for Updates",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
            command=self._check_ytdlp_update,
        )
        self._update_btn.grid(row=0, column=0)

        self._update_status = ctk.CTkLabel(
            update_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=CLR_MUTED,
        )
        self._update_status.grid(row=0, column=1, padx=(10, 0), sticky="w")
        row += 1

        # -- FFmpeg Status --------------------------------------------------
        self._section_label(container, LBL_FFMPEG_STATUS, row)
        row += 1

        ffmpeg_frame = ctk.CTkFrame(container, fg_color="transparent")
        ffmpeg_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        ffmpeg_frame.grid_columnconfigure(1, weight=1)

        self._ffmpeg_status = ctk.CTkLabel(
            ffmpeg_frame,
            text=ffmpeg_manager.get_ffmpeg_status(),
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self._ffmpeg_status.grid(row=0, column=0, sticky="w")

        self._ffmpeg_btn = ctk.CTkButton(
            ffmpeg_frame,
            text=LBL_FFMPEG_DOWNLOAD,
            width=140,
            height=34,
            corner_radius=8,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._download_ffmpeg,
        )
        # Only show download button if FFmpeg is not found
        if ffmpeg_manager.get_ffmpeg_path() is None:
            self._ffmpeg_btn.grid(row=0, column=1, padx=(10, 0), sticky="e")
        row += 1

        # -- Close button ---------------------------------------------------
        close_btn = ctk.CTkButton(
            container,
            text=LBL_CLOSE,
            width=100,
            height=38,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._on_close,
        )
        close_btn.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky="e")

    # -- helpers ------------------------------------------------------------

    def _section_label(self, parent: Any, text: str, row: int) -> None:
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        lbl.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))

    # -- handlers -----------------------------------------------------------

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(
            initialdir=self._output_var.get(),
            title="Select Output Folder",
        )
        if folder:
            self._output_var.set(folder)
            self._settings.set("output_folder", folder)

    def _browse_cookies(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Select Cookies File",
        )
        if path:
            self._cookies_var.set(path)
            self._settings.set("cookies_file", path)

    def _on_theme_selected(self) -> None:
        theme = self._theme_var.get().lower()
        self._settings.set("theme", theme)
        self._on_theme_change(theme)
        # Re-focus after CTk redraws everything
        self.after(100, self._refocus)

    def _refocus(self) -> None:
        """Re-focus and lift after theme redraw."""
        try:
            self.focus_force()
            self.lift()
        except Exception:
            pass

    def _on_format_selected(self) -> None:
        label = self._format_var.get()
        key = FORMAT_OPTIONS.get(label, "remember")
        self._settings.set("default_format", key)

    def _on_concurrent_changed(self, value: float) -> None:
        n = int(value)
        self._concurrent_label.configure(text=str(n))
        self._settings.set("max_concurrent", n)
        self._on_max_concurrent_change(n)

    def _check_ytdlp_update(self) -> None:
        self._update_btn.configure(state="disabled", text="Checking…")
        self._update_status.configure(text="", text_color=CLR_MUTED)

        def _worker() -> None:
            if getattr(sys, 'frozen', False):
                try:
                    import yt_dlp.version
                    import urllib.request
                    import json
                    current_ver = yt_dlp.version.__version__
                    req = urllib.request.Request("https://pypi.org/pypi/yt-dlp/json", headers={"User-Agent": "YDrop"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                        latest_ver = data["info"]["version"]
                    
                    if current_ver == latest_ver:
                        msg = f"yt-dlp is up to date (v{current_ver})."
                        color = CLR_SUCCESS
                    else:
                        msg = f"Built-in: v{current_ver} | Latest: v{latest_ver}. Check for YDrop updates."
                        color = CLR_MUTED
                except Exception:
                    msg = "Built-in yt-dlp cannot be updated in .exe."
                    color = CLR_MUTED

                self.after(0, lambda: self._update_status.configure(text=msg, text_color=color))
                self.after(0, lambda: self._update_btn.configure(state="normal", text="Check for Updates"))
                return

            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = result.stdout + result.stderr
                if "already satisfied" in output.lower():
                    msg = "yt-dlp is up to date."
                    color = CLR_SUCCESS
                elif "successfully installed" in output.lower():
                    msg = "yt-dlp updated successfully. Restart app."
                    color = CLR_SUCCESS
                else:
                    msg = "Update check completed."
                    color = CLR_MUTED
            except Exception as exc:
                msg = f"Update failed: {exc}"
                color = CLR_ERROR

            self.after(0, lambda: self._update_status.configure(text=msg, text_color=color))
            self.after(0, lambda: self._update_btn.configure(state="normal", text="Check for Updates"))

        threading.Thread(target=_worker, daemon=True).start()

    def _download_ffmpeg(self) -> None:
        self._ffmpeg_btn.configure(state="disabled", text="Downloading…")

        def _progress(status: str, pct: int) -> None:
            self.after(0, lambda: self._ffmpeg_status.configure(text=status))

        def _worker() -> None:
            result = ffmpeg_manager.download_ffmpeg(callback=_progress)
            if result:
                self.after(0, lambda: self._ffmpeg_status.configure(
                    text=f"✓ Downloaded to {result}",
                    text_color=CLR_SUCCESS,
                ))
                self.after(0, lambda: self._ffmpeg_btn.grid_forget())
            else:
                self.after(0, lambda: self._ffmpeg_btn.configure(
                    state="normal", text=LBL_FFMPEG_DOWNLOAD,
                ))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_close(self) -> None:
        # Save cookies and output on close
        cookies = self._cookies_var.get().strip()
        self._settings.set("cookies_file", cookies)
        output = self._output_var.get().strip()
        if output:
            self._settings.set("output_folder", output)
        self.destroy()
