"""
YDrop — Queue view component.

Scrollable container of DownloadCard widgets. Manages card lifecycle
(create, update, remove) and header with active/done counts.
"""

import os
import customtkinter as ctk
from typing import Any, Callable, Optional

from core.downloader import DownloadItem, DownloadQueue
from ui.components.download_card import DownloadCard

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LBL_HEADER = "Downloads"
LBL_EMPTY = "No downloads yet. Paste a URL and add to queue."

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

CLR_MUTED = "#8B8FA3"


class QueueView(ctk.CTkFrame):
    """
    Scrollable queue view that hosts DownloadCard instances.

    Receives update notifications from DownloadQueue via callback.
    """

    def __init__(
        self,
        master: Any,
        queue: DownloadQueue,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._queue = queue
        self._cards: dict[str, DownloadCard] = {}
        self._format_displays: dict[str, str] = {}  # item_id -> format label

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -- header ---------------------------------------------------------
        self._header = ctk.CTkLabel(
            self,
            text=LBL_HEADER,
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 8))

        # -- scrollable container -------------------------------------------
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=10,
        )
        self._scroll_frame.grid(row=1, column=0, sticky="nsew")
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        # -- empty label ----------------------------------------------------
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text=LBL_EMPTY,
            font=ctk.CTkFont(size=13),
            text_color=CLR_MUTED,
        )
        self._empty_label.grid(row=0, column=0, pady=40)

        # Register as queue callback
        self._queue.set_update_callback(self._on_queue_update)

    # -- public api ---------------------------------------------------------

    def set_format_display(self, item_id: str, text: str) -> None:
        """Store the format display string for a card."""
        self._format_displays[item_id] = text

    # -- callbacks ----------------------------------------------------------

    def _on_queue_update(self, item_id: str, item: DownloadItem) -> None:
        """
        Called by DownloadQueue from a worker thread.
        Schedule actual UI work on the main thread.
        """
        self.after(0, lambda: self._process_update(item_id, item))

    def _process_update(self, item_id: str, item: DownloadItem) -> None:
        """Main-thread: create, update, or remove cards."""
        # Check if item was removed from queue
        if self._queue.get_item(item_id) is None:
            card = self._cards.pop(item_id, None)
            if card:
                card.destroy()
            self._update_header()
            self._update_empty_state()
            return

        # Existing card — update
        if item_id in self._cards:
            self._cards[item_id].configure_from_item(item)
            self._update_header()
            return

        # New card — create
        self._empty_label.grid_forget()

        card = DownloadCard(
            self._scroll_frame,
            item=item,
            on_cancel=self._handle_cancel,
            on_retry=self._handle_retry,
            on_remove=self._handle_remove,
            on_open_folder=self._handle_open_folder,
        )

        # Apply stored format display
        fmt_display = self._format_displays.get(item_id, "")
        if fmt_display:
            card.set_format_display(fmt_display)
            card.configure_from_item(item)  # re-render with format info

        row = len(self._cards)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        self._cards[item_id] = card
        self._update_header()

    def _update_header(self) -> None:
        """Update header with active/done counts."""
        active = self._queue.active_count()
        done = self._queue.done_count()
        parts = []
        if active > 0:
            parts.append(f"{active} active")
        if done > 0:
            parts.append(f"{done} done")
        suffix = f"  ({' · '.join(parts)})" if parts else ""
        self._header.configure(text=f"{LBL_HEADER}{suffix}")

    def _update_empty_state(self) -> None:
        """Show empty label if no cards remain."""
        if not self._cards:
            self._empty_label.grid(row=0, column=0, pady=40)

    # -- action handlers ----------------------------------------------------

    def _handle_cancel(self, item_id: str) -> None:
        self._queue.cancel(item_id)

    def _handle_retry(self, item_id: str) -> None:
        self._queue.retry(item_id)

    def _handle_remove(self, item_id: str) -> None:
        self._queue.remove(item_id)
        card = self._cards.pop(item_id, None)
        if card:
            card.destroy()
        self._format_displays.pop(item_id, None)
        # Re-grid remaining cards
        for i, (cid, c) in enumerate(self._cards.items()):
            c.grid(row=i, column=0, sticky="ew", pady=(0, 8))
        self._update_header()
        self._update_empty_state()

    def _handle_open_folder(self, folder_path: str) -> None:
        """Open the output folder in Windows Explorer."""
        try:
            os.startfile(folder_path)
        except Exception:
            pass
