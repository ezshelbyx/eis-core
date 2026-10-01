"""Administrator privilege detection and controlled elevation for Windows."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def is_admin() -> bool:
    """True when the current process has administrator rights."""
    try:
        if os.name == "nt":
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        # POSIX: root check (mainly for development on Linux/macOS).
        return os.geteuid() == 0
    except Exception:  # pragma: no cover - defensive
        return False


def current_user() -> str:
    try:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    except Exception:  # pragma: no cover
        return "unknown"


def is_windows() -> bool:
    return os.name == "nt"


def require_elevation_hint(feature: str) -> dict:
    """Return a standard payload used by UIs when a feature needs elevation."""
    return {
        "ok": False,
        "needs_elevation": True,
        "error": f"'{feature}' requires administrator rights.",
        "hint": "Restart E.I.S. Core as administrator (see docs/INSTALL.md).",
    }


def elevate_and_wait(purpose: str = "E.I.S. Core") -> dict:
    """Relaunch E.I.S. Core elevated via UAC and wait for user consent.

    Returns ``{"ok": True, "elevated": True}`` when the user accepted the UAC
    prompt (the elevated instance takes over), ``{"ok": False, ...}`` when
    declined/unavailable.  This never silently elevates: Windows itself asks.
    """
    if not is_windows():
        return {"ok": False, "error": "Elevation is Windows-only."}
    if is_admin():
        return {"ok": True, "elevated": True, "already_admin": True}

    python = sys.executable
    script = sys.argv[0] if sys.argv and sys.argv[0] else "-m eis.app"
    params = f'"{python}" "{script}"'
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", f"/c {params}", None, 0  # SW_HIDE
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Elevation failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    if rc > 32:
        log.info("Elevation requested for: %s", purpose)
        return {"ok": True, "elevated": True}
    return {"ok": False, "error": f"ShellExecuteW returned {rc} (user declined or error)."}


def run_elevated(command: list[str] | str, timeout: int = 600) -> dict:
    """Run a single command elevated and capture output.

    Used only by explicit user actions (SFC, DISM, ...) that require admin.
    Output is captured to a temp file because ``runas`` cannot pipe stdout.
    """
    if not is_windows():
        return {"ok": False, "error": "Elevation is Windows-only."}
    import tempfile

    if isinstance(command, str):
        command = [command]
    out_path = Path(tempfile.gettempdir()) / "eis_elevated_out.txt"
    try:
        out_path.unlink(missing_ok=True)
    except OSError:
        pass

    inner = subprocess.list2cmdline(list(command))
    args = f'/c {inner} > "{out_path}" 2>&1'
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", args, None, 0  # SW_HIDE
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if rc <= 32:
        return {"ok": False, "error": "User declined the elevation prompt."}

    # Poll for completion (output file appears when cmd finishes).
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if out_path.exists():
            # Give cmd a moment to finish writing.
            time.sleep(1.0)
            try:
                text = out_path.read_text(encoding="utf-8", errors="replace")
                return {"ok": True, "returncode": 0, "stdout": text, "stderr": ""}
            except OSError:
                continue
        time.sleep(1.0)
    return {"ok": False, "error": "Timed out waiting for elevated command.", "timeout": True}

