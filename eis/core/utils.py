"""Small configuration/naming helpers shared across E.I.S. Core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from eis import APP_NAME, APP_VERSION


def app_title(version: bool = True) -> str:
    """Return the full window title, e.g. ``E.I.S. Core 0.1.0``."""
    return f"{APP_NAME} {APP_VERSION}" if version else APP_NAME


def format_bytes(num: float, decimals: int = 1) -> str:
    """Human-readable byte size: 1536 -> '1.5 KB'."""
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num)
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.{decimals}f} {unit}"
        value /= 1024.0
    return f"{value:.{decimals}f} EB"


def format_duration(seconds: float) -> str:
    """Human-readable uptime: 90061 -> '1d 1h 1m 1s'."""
    seconds = int(max(0, seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def format_percent(value: float, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "n/a"


def safe_filename(name: str, max_len: int = 80) -> str:
    """Sanitize a string for use as a filename."""
    keep = "".join(c if c.isalnum() or c in " -_." else "_" for c in name)
    keep = keep.strip().strip(".") or "untitled"
    return keep[:max_len]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file, streamed (used for build manifests)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jdump(obj: Any, indent: int = 2) -> str:
    """Pretty JSON dump with stable key ordering and UTF-8."""
    return json.dumps(obj, indent=indent, default=str, ensure_ascii=False, sort_keys=True)


def merge_dict(base: dict, override: dict) -> dict:
    """Recursive dict merge - returns a new dict."""
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = merge_dict(out[key], val)
        else:
            out[key] = val
    return out
