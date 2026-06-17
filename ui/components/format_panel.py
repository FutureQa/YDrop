"""
YDrop — Format selection panel component.

Radio buttons for Video / Audio / Custom, quality dropdowns, output folder picker.
"""

import customtkinter as ctk
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Labels & options
# ---------------------------------------------------------------------------

LBL_VIDEO = "Video"
LBL_AUDIO = "Audio only"
LBL_CUSTOM = "Custom"
LBL_ADD_QUEUE = "+ Add to Queue"
LBL_CUSTOM_PLACEHOLDER = "e.g. bestvideo[height<=720]+bestaudio"

VIDEO_QUALITY = ["Best Quality", "4K", "1440p", "1080p", "720p", "480p", "360p"]
VIDEO_CONTAINER = ["MP4", "MKV", "WEBM"]
VIDEO_CODEC = {"Any Codec": "", "H.264": "avc1", "AV1": "av01", "VP9": "vp9"}

AUDIO_FORMAT = ["MP3", "M4A", "FLAC", "WAV", "OGG"]
AUDIO_QUALITY = ["Best Quality", "320k", "256k", "192k", "128k", "64k"]

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

CLR_ACCENT = "#6366F1"
CLR_ACCENT_HOVER = "#818CF8"

class FormatPanel(ctk.CTkFrame):
    """
    Format type selection (radio), quality/codec/container dropdowns, and
    Add to Queue button. Output folder picker has been moved to settings.
    """

    def __init__(
        self,
        master: Any,
        initial_format_type: str = "video",
        initial_video_q: str = "Best Quality",
        initial_video_c: str = "MP4",
        initial_video_vcodec: str = "Any Codec",
        initial_audio_f: str = "MP3",
        initial_audio_q: str = "320k",
        initial_custom: str = "",
        on_add_to_queue: Optional[Callable[[], None]] = None,
        on_format_change: Optional[Callable[[str, str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=12, **kwargs)

        self._on_add_to_queue = on_add_to_queue
        self._on_format_change = on_format_change

        self.grid_columnconfigure(1, weight=1)

        # -- format type radio buttons (left side) -------------------------
        self._format_var = ctk.StringVar(value=initial_format_type)

        radio_frame = ctk.CTkFrame(self, fg_color="transparent")
        radio_frame.grid(row=0, column=0, rowspan=4, sticky="nw", padx=(16, 12), pady=16)

        self._radio_video = ctk.CTkRadioButton(
            radio_frame,
            text=LBL_VIDEO,
            variable=self._format_var,
            value="video",
            font=ctk.CTkFont(size=14),
            command=self._on_type_changed,
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
        )
        self._radio_video.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._radio_audio = ctk.CTkRadioButton(
            radio_frame,
            text=LBL_AUDIO,
            variable=self._format_var,
            value="audio",
            font=ctk.CTkFont(size=14),
            command=self._on_type_changed,
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
        )
        self._radio_audio.grid(row=1, column=0, sticky="w", pady=(0, 6))

        self._radio_custom = ctk.CTkRadioButton(
            radio_frame,
            text=LBL_CUSTOM,
            variable=self._format_var,
            value="custom",
            font=ctk.CTkFont(size=14),
            command=self._on_type_changed,
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
        )
        self._radio_custom.grid(row=2, column=0, sticky="w")

        # -- right side: dropdowns -----------------------------------------
        self._right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._right_frame.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=(0, 16), pady=16)
        self._right_frame.grid_columnconfigure(1, weight=1)

        # Row 0
        self._row0_label = ctk.CTkLabel(self._right_frame, text="", font=ctk.CTkFont(size=13), anchor="w")
        self._row0_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._row0_drop = self._create_dropdown(self._right_frame)
        self._row0_drop.grid(row=0, column=1, sticky="ew")

        # Row 1
        self._row1_label = ctk.CTkLabel(self._right_frame, text="", font=ctk.CTkFont(size=13), anchor="w")
        self._row1_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        self._row1_drop = self._create_dropdown(self._right_frame)
        self._row1_drop.grid(row=1, column=1, sticky="ew", pady=(10, 0))

        # Row 2
        self._row2_label = ctk.CTkLabel(self._right_frame, text="", font=ctk.CTkFont(size=13), anchor="w")
        self._row2_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        self._row2_drop = self._create_dropdown(self._right_frame)
        self._row2_drop.grid(row=2, column=1, sticky="ew", pady=(10, 0))

        # Custom entry (replaces Row 0 when custom is selected)
        self._custom_var = ctk.StringVar(value=initial_custom)
        self._custom_entry = ctk.CTkEntry(
            self._right_frame,
            textvariable=self._custom_var,
            placeholder_text=LBL_CUSTOM_PLACEHOLDER,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
        )

        # Initialize values
        self._video_q_var = ctk.StringVar(value=initial_video_q if initial_video_q in VIDEO_QUALITY else VIDEO_QUALITY[0])
        self._video_c_var = ctk.StringVar(value=initial_video_c if initial_video_c in VIDEO_CONTAINER else VIDEO_CONTAINER[0])
        self._video_codec_var = ctk.StringVar(value=initial_video_vcodec if initial_video_vcodec in VIDEO_CODEC else list(VIDEO_CODEC.keys())[0])
        
        self._audio_f_var = ctk.StringVar(value=initial_audio_f if initial_audio_f in AUDIO_FORMAT else AUDIO_FORMAT[0])
        self._audio_q_var = ctk.StringVar(value=initial_audio_q if initial_audio_q in AUDIO_QUALITY else AUDIO_QUALITY[0])

        # Add to Queue button
        self._add_btn = ctk.CTkButton(
            self._right_frame,
            text=LBL_ADD_QUEUE,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=CLR_ACCENT,
            hover_color=CLR_ACCENT_HOVER,
            command=self._on_add_clicked,
        )
        self._add_btn.grid(row=3, column=0, columnspan=2, sticky="e", pady=(16, 0))

        # Initialize visibility
        self._on_type_changed()

    def _create_dropdown(self, parent: Any) -> ctk.CTkOptionMenu:
        return ctk.CTkOptionMenu(
            parent,
            values=[""],
            width=200,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color="#374151",
            button_color="#4B5563",
            button_hover_color="#6B7280",
            command=self._on_quality_changed,
        )

    # -- public api ---------------------------------------------------------

    def get_format_type(self) -> str:
        """Return 'video', 'audio', or 'custom'."""
        return self._format_var.get()

    def get_format_key(self) -> str:
        """Return structured format string like 'video|1080p|MP4|avc1' or 'audio|MP3|320k'."""
        ft = self._format_var.get()
        if ft == "video":
            q = self._video_q_var.get()
            c = self._video_c_var.get()
            codec_label = self._video_codec_var.get()
            codec_key = VIDEO_CODEC.get(codec_label, "")
            return f"video|{q}|{c}|{codec_key}"
        elif ft == "audio":
            f = self._audio_f_var.get()
            q = self._audio_q_var.get()
            return f"audio|{f}|{q}"
        else:
            return self._custom_var.get().strip() or "bestvideo+bestaudio/best"

    def get_format_display(self) -> str:
        """Return human-readable format label for the download card."""
        ft = self._format_var.get()
        if ft == "video":
            return f"Video {self._video_q_var.get()} ({self._video_c_var.get()})"
        elif ft == "audio":
            q = self._audio_q_var.get()
            return f"Audio {self._audio_f_var.get()}" + (f" {q}" if q != "Best Quality" else "")
        else:
            return "Custom"

    def get_state(self) -> dict[str, str]:
        """Get the current UI state to save to settings."""
        return {
            "format_type": self.get_format_type(),
            "video_q": self._video_q_var.get(),
            "video_c": self._video_c_var.get(),
            "video_vcodec": self._video_codec_var.get(),
            "audio_f": self._audio_f_var.get(),
            "audio_q": self._audio_q_var.get(),
            "custom": self._custom_var.get(),
        }

    # -- handlers -----------------------------------------------------------

    def _on_type_changed(self) -> None:
        ft = self._format_var.get()

        # Hide all rows first
        for w in (self._row0_label, self._row0_drop, self._row1_label, self._row1_drop, self._row2_label, self._row2_drop, self._custom_entry):
            w.grid_forget()

        if ft == "video":
            self._row0_label.configure(text="Quality:")
            self._row0_drop.configure(values=VIDEO_QUALITY, variable=self._video_q_var)
            self._row0_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
            self._row0_drop.grid(row=0, column=1, sticky="ew")

            self._row1_label.configure(text="Format:")
            self._row1_drop.configure(values=VIDEO_CONTAINER, variable=self._video_c_var)
            self._row1_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
            self._row1_drop.grid(row=1, column=1, sticky="ew", pady=(10, 0))

            self._row2_label.configure(text="Codec:")
            self._row2_drop.configure(values=list(VIDEO_CODEC.keys()), variable=self._video_codec_var)
            self._row2_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
            self._row2_drop.grid(row=2, column=1, sticky="ew", pady=(10, 0))

        elif ft == "audio":
            self._row0_label.configure(text="Format:")
            self._row0_drop.configure(values=AUDIO_FORMAT, variable=self._audio_f_var)
            self._row0_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
            self._row0_drop.grid(row=0, column=1, sticky="ew")

            self._row1_label.configure(text="Quality:")
            self._row1_drop.configure(values=AUDIO_QUALITY, variable=self._audio_q_var)
            self._row1_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
            self._row1_drop.grid(row=1, column=1, sticky="ew", pady=(10, 0))

        else:
            self._row0_label.configure(text="Format:")
            self._row0_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
            self._custom_entry.grid(row=0, column=1, sticky="ew")

        if self._on_format_change:
            self._on_format_change(ft, self.get_format_key())

    def _on_quality_changed(self, _value: str = "") -> None:
        if self._on_format_change:
            self._on_format_change(self.get_format_type(), self.get_format_key())

    def _on_add_clicked(self) -> None:
        if self._on_add_to_queue:
            self._on_add_to_queue()
