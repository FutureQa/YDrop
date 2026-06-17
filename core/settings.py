"""
YDrop — Settings persistence.

Stores user preferences as JSON in AppData/Local/YDrop/settings.json.
Creates directory and defaults on first run. Saves on every mutation.
"""

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "output_folder": str(Path.home() / "Downloads"),
    "theme": "system",
    "default_format": "remember",
    "max_concurrent": 3,
    "cookies_file": "",
    "last_format_type": "video",
    "last_video_quality": "best",
    "last_audio_format": "mp3_320",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YDrop"
_SETTINGS_FILE = _APP_DIR / "settings.json"


class Settings:
    """Thread-safe settings manager backed by a JSON file."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    # -- public api ---------------------------------------------------------

    def get(self, key: str) -> Any:
        """Return setting value, falling back to default."""
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        """Update a setting and persist to disk immediately."""
        self._data[key] = value
        self._save()

    def reset(self) -> None:
        """Reset all settings to defaults."""
        self._data = dict(DEFAULTS)
        self._save()

    @property
    def data(self) -> dict[str, Any]:
        """Return a shallow copy of current settings."""
        return dict(self._data)

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        """Load settings from disk, merging with defaults."""
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                # Merge — stored values override defaults, new defaults fill gaps
                for k, v in stored.items():
                    if k in DEFAULTS:
                        self._data[k] = v
            except (json.JSONDecodeError, OSError):
                pass  # corrupt file — keep defaults
        else:
            self._save()  # create file with defaults on first run

    def _save(self) -> None:
        """Persist current settings to disk."""
        _APP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass  # non-critical — continue without save
