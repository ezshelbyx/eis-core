"""JSON-backed application settings for E.I.S. Core.

Settings live in ``data/settings.json`` and are always merged over
``DEFAULTS``, so a missing or hand-edited file can never break the
application.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from eis.core.logging_config import SETTINGS_PATH, ensure_runtime_dirs

DEFAULTS: dict[str, Any] = {
    # --- appearance -------------------------------------------------
    "appearance.mode": "system",          # light | dark | system
    "appearance.theme": "eis-dark",       # eis-dark | eis-light
    "appearance.font_size": 10,           # base UI font size (pt)
    "appearance.window_geometry": "1280x800",
    "appearance.window_maximized": True,
    # --- language ---------------------------------------------------
    "general.language": "en",
    # --- logging ----------------------------------------------------
    "logging.level": "INFO",              # DEBUG | INFO | WARNING | ERROR
    "logging.console": True,
    "logging.record_commands": True,      # write data/logs/command_history.jsonl
    # --- safety -----------------------------------------------------
    "safety.require_confirmation": True,  # confirm every destructive action
    "safety.allow_privilege_elevation": True,
    "safety.block_system_dirs": True,     # duplicate finder / cleaner guard
    # --- network ----------------------------------------------------
    "network.default_ping_count": 4,
    "network.default_timeout_ms": 1000,
    "network.discovery_timeout_s": 5,
    # --- android ----------------------------------------------------
    "android.adb_path": "",               # auto-detected when empty
    "android.fastboot_path": "",
    # --- tools ------------------------------------------------------
    "tools.prefer_psutil": True,          # use psutil when installed
    "tools.cleaner_locations": [],        # extra user-defined cleanup dirs
    "tools.report_format": "html",        # default export format
    "tools.kb_search_limit": 40,
    # --- advanced ---------------------------------------------------
    "advanced.debug": False,
}


class Settings:
    """Thread-safe JSON settings store with defaults merging."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else SETTINGS_PATH
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load settings from disk, merged over DEFAULTS."""
        with self._lock:
            self._data = dict(DEFAULTS)
            try:
                if self.path.exists():
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._data.update(raw)
            except (OSError, json.JSONDecodeError):
                # Corrupt settings file: keep defaults, do not crash.
                self._data = dict(DEFAULTS)
            self._normalize()

    # ------------------------------------------------------------------
    def save(self) -> None:
        """Persist current settings to disk as pretty JSON."""
        with self._lock:
            ensure_runtime_dirs()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.path)

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                return self._data[key]
            return DEFAULTS.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        with self._lock:
            self._data[key] = value
            if save:
                self.save()

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def reset(self) -> None:
        """Restore factory defaults."""
        with self._lock:
            self._data = dict(DEFAULTS)
            self.save()

    # ------------------------------------------------------------------
    def _normalize(self) -> None:
        """Coerce values that must have a specific type."""
        try:
            self._data["appearance.font_size"] = max(8, min(16, int(self._data["appearance.font_size"])))
        except (KeyError, TypeError, ValueError):
            self._data["appearance.font_size"] = DEFAULTS["appearance.font_size"]
        for key in ("network.default_ping_count", "network.discovery_timeout_s"):
            try:
                self._data[key] = max(1, min(50, int(self._data[key])))
            except (KeyError, TypeError, ValueError):
                self._data[key] = DEFAULTS[key]
        if self._data.get("appearance.mode") not in ("light", "dark", "system"):
            self._data["appearance.mode"] = "system"
        if self._data.get("general.language") not in ("en",):
            self._data["general.language"] = "en"


_instance: Settings | None = None
_instance_lock = threading.Lock()


def get_settings() -> Settings:
    """Return the process-wide Settings singleton."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = Settings()
        return _instance
