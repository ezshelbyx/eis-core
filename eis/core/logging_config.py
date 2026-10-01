"""Application-wide paths and logging setup for E.I.S. Core."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from eis import APP_NAME

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
REPORT_DIR = DATA_DIR / "reports"
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"
DOWNLOAD_DIR = DATA_DIR / "downloads"
DB_PATH = DATA_DIR / "eis.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
KB_CUSTOM_PATH = DATA_DIR / "kb_custom.json"
COMMAND_LOG_PATH = LOG_DIR / "command_history.jsonl"

DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_console_handler: logging.Handler | None = None


def ensure_runtime_dirs() -> None:
    """Create the runtime data directories (idempotent)."""
    for d in (DATA_DIR, LOG_DIR, REPORT_DIR, BACKUP_DIR, EXPORT_DIR, DOWNLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _resolve_level(name: str | None) -> int:
    if not name:
        return DEFAULT_LOG_LEVEL
    return getattr(logging, str(name).upper(), DEFAULT_LOG_LEVEL)


def setup_logging(level: str | None = None, console: bool = True) -> Path:
    """Configure application logging.

    Writes to ``data/logs/eis.log`` (rotating, 1 MB x 3 backups) and prints to
    stderr when *console* is true.  Safe to call more than once: existing
    handlers on the root logger are reused.
    """
    ensure_runtime_dirs()
    root = logging.getLogger()
    root.setLevel(_resolve_level(level))

    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "eis.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        root.addHandler(file_handler)

    global _console_handler
    if console and _console_handler is None:
        _console_handler = logging.StreamHandler(sys.stderr)
        _console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        root.addHandler(_console_handler)

    return LOG_DIR / "eis.log"


def set_console_logging(enabled: bool) -> None:
    """Attach/detach the stderr console handler (used by the Settings view)."""
    global _console_handler
    root = logging.getLogger()
    if enabled and _console_handler is None:
        _console_handler = logging.StreamHandler(sys.stderr)
        _console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        root.addHandler(_console_handler)
    elif not enabled and _console_handler is not None:
        root.removeHandler(_console_handler)
        _console_handler = None


def get_log_path() -> Path:
    return LOG_DIR / "eis.log"


def get_app_log_tail(lines: int = 200) -> str:
    """Return the last *lines* lines of the application log (for the UI)."""
    path = get_log_path()
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except OSError as exc:  # pragma: no cover - defensive
        return f"[unable to read log: {exc}]"


def is_windows() -> bool:
    return os.name == "nt"


def windows_only(func):
    """Decorator: returns a friendly error payload on non-Windows platforms."""

    def wrapper(*args, **kwargs):
        if not is_windows():
            return {"ok": False, "error": "This feature requires Windows."}
        return func(*args, **kwargs)

    wrapper.__name__ = getattr(func, "__name__", "wrapper")
    wrapper.__doc__ = func.__doc__
    return wrapper
