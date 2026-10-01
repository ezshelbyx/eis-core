"""File metadata inspector: size, timestamps, attributes, hashes."""

from __future__ import annotations

import logging
import os
import stat
from datetime import datetime
from pathlib import Path

from eis.modules.files.hashing import hash_file

log = logging.getLogger(__name__)


def inspect(path: str | Path, include_hashes: bool = True, algorithms: tuple[str, ...] = ("md5", "sha256")) -> dict:
    """Full metadata payload for one file or directory."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"Path not found: {p}"}
    try:
        st = p.stat()
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    info: dict = {
        "ok": True,
        "path": str(p),
        "name": p.name,
        "type": "directory" if p.is_dir() else "file",
        "size_bytes": st.st_size if p.is_file() else _dir_size(p),
        "created": _ts(getattr(st, "st_birthtime", st.st_ctime)),
        "modified": _ts(st.st_mtime),
        "accessed": _ts(st.st_atime),
        "hidden": _is_hidden(p),
        "read_only": not (st.st_mode & stat.S_IWRITE or st.st_mode & stat.S_IWUSR),
        "extension": p.suffix.lower(),
        "owner": _owner(st),
    }
    if p.is_dir():
        info["files_inside"] = _count_entries(p)
    if include_hashes and p.is_file():
        res = hash_file(p, algorithms)
        if res["ok"]:
            info["hashes"] = res["hashes"]
    info["attributes"] = _win_attributes(p) if os.name == "nt" else _posix_mode(st)
    return info


def _ts(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return ""


def _is_hidden(p: Path) -> bool:
    if os.name == "nt":
        try:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
            return bool(attrs & 0x2) if attrs != -1 else False
        except Exception:
            return False
    return p.name.startswith(".")


def _owner(st) -> str:
    try:
        import pwd  # type: ignore

        return pwd.getpwuid(st.st_uid).pw_name
    except (ImportError, KeyError):
        return ""


def _win_attributes(p: Path) -> str:
    flags = []
    try:
        import ctypes

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
        if attrs == -1:
            return ""
        if attrs & 0x2:
            flags.append("Hidden")
        if attrs & 0x4:
            flags.append("System")
        if attrs & 0x1:
            flags.append("ReadOnly")
        if attrs & 0x20:
            flags.append("Archive")
        if attrs & 0x400:
            flags.append("ReparsePoint")
    except Exception:
        return ""
    return ", ".join(flags) or "Normal"


def _posix_mode(st) -> str:
    return stat.filemode(st.st_mode)


def _dir_size(root: Path, max_files: int = 20000) -> int:
    total = 0
    count = 0
    try:
        for item in root.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
                count += 1
                if count >= max_files:
                    break
    except OSError:
        pass
    return total


def _count_entries(root: Path) -> int:
    try:
        return sum(1 for _ in root.iterdir())
    except OSError:
        return 0
