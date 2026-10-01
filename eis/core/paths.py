"""Command history recorder for E.I.S. Core.

Appends every notable action to ``data/logs/command_history.jsonl`` and keeps
an in-memory ring buffer for the UI (Activity tab in Settings).
"""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eis.core.logging_config import COMMAND_LOG_PATH, ensure_runtime_dirs
from eis.core.settings import get_settings

_BUFFER_MAX = 500
_buffer: deque[dict] = deque(maxlen=_BUFFER_MAX)
_lock = threading.Lock()


def record_command(
    action: str,
    command: str = "",
    result: str = "ok",
    error: str = "",
    details: dict[str, Any] | None = None,
) -> dict:
    """Record one executed action.  Returns the stored entry."""
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "command": command,
        "result": result,
        "error": error,
        "details": details or {},
    }
    settings = get_settings()
    if settings.get("logging.record_commands", True):
        try:
            ensure_runtime_dirs()
            with _lock:
                COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with COMMAND_LOG_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # logging must never break a tool
    with _lock:
        _buffer.append(entry)
    return entry


def recent(limit: int = 100) -> list[dict]:
    """Most recent entries, newest first (in-memory buffer)."""
    with _lock:
        items = list(_buffer)[-limit:]
    return list(reversed(items))


def read_history(limit: int = 500) -> list[dict]:
    """Read history from disk (newest first)."""
    path: Path = COMMAND_LOG_PATH
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    except OSError:
        return []


def clear_history() -> int:
    """Clear the on-disk history.  Returns entries removed."""
    with _lock:
        count = len(_buffer)
        _buffer.clear()
    path = COMMAND_LOG_PATH
    if path.exists():
        try:
            count = max(count, len(path.read_text(encoding="utf-8", errors="replace").splitlines()))
            path.unlink()
        except OSError:
            pass
    return count


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
