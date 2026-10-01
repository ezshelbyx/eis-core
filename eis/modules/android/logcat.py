"""Logcat viewer: buffered capture with filtering, search and export."""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from eis.core.command_runner import CommandResult, run_command
from eis.core.logging_config import EXPORT_DIR
from eis.core.paths import record_command
from eis.modules.android.adb import adb_path

log = logging.getLogger(__name__)

LEVELS = ("V", "D", "I", "W", "E", "F")
_LEVEL_NAMES = {"V": "Verbose", "D": "Debug", "I": "Info", "W": "Warning", "E": "Error", "F": "Fatal"}
_LINE_RE = re.compile(r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+([VDIWEF])\s*/\s*([^(]*?)\(\s*(\d+)\):\s(.*)$")


class LogcatBuffer:
    """Reads logcat in chunks into a bounded in-memory buffer (thread-safe)."""

    def __init__(self, max_lines: int = 5000):
        self.max_lines = max_lines
        self.lines: list[dict] = []
        self.lock = threading.Lock()
        self.running = False
        self.paused = False
        self._thread = None
        self._process = None

    # ------------------------------------------------------------------
    def start(self, serial: str = "", min_level: str = "V", filter_tag: str = "") -> bool:
        if not adb_path():
            return False
        if self.running:
            self.stop()
        self.running = True
        self.paused = False
        self._thread = threading.Thread(
            target=self._reader, args=(serial, min_level, filter_tag), daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self._process:
            try:
                self._process.terminate()
            except Exception:  # pragma: no cover
                pass
            self._process = None

    def clear_screen_only(self) -> None:
        """UI 'Clear' - empties the visible buffer without touching the device."""
        with self.lock:
            self.lines.clear()

    def clear_device(self, serial: str = "") -> dict:
        """Sends 'logcat -c' to the device (clears device-side ring buffer)."""
        adb = adb_path()
        if not adb:
            return {"ok": False, "error": "ADB not found."}
        argv = [adb] + (["-s", serial] if serial else []) + ["logcat", "-c"]
        res = run_command(argv, timeout=15, check_safety=False)
        with self.lock:
            self.lines.clear()
        record_command("android.logcat_clear", command="adb logcat -c", result="ok" if res.ok else "error")
        return {"ok": res.ok, "error": res.stderr}

    # ------------------------------------------------------------------
    def _reader(self, serial: str, min_level: str, filter_tag: str) -> None:
        adb = adb_path()
        argv = [adb] + (["-s", serial] if serial else []) + [
            "logcat", "-v", "threadtime", f"*:{min_level.upper()}"
        ]
        if filter_tag:
            argv.append(filter_tag)
        try:
            import subprocess

            self._process = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                encoding="utf-8", errors="replace",
            )
            assert self._process.stdout is not None
            for raw in self._process.stdout:
                if not self.running:
                    break
                if self.paused:
                    time.sleep(0.05)
                    continue
                entry = self._parse_line(raw.rstrip())
                with self.lock:
                    self.lines.append(entry)
                    if len(self.lines) > self.max_lines:
                        self.lines = self.lines[-self.max_lines:]
        except Exception as exc:  # pragma: no cover
            log.debug("logcat reader stopped: %s", exc)
        finally:
            self.running = False

    @staticmethod
    def _parse_line(raw: str) -> dict:
        m = _LINE_RE.match(raw)
        if m:
            return {
                "time": m.group(1), "level": m.group(2), "tag": m.group(3).strip(),
                "pid": m.group(4), "message": m.group(5), "raw": raw,
            }
        return {"time": "", "level": "?", "tag": "", "pid": "", "message": raw, "raw": raw}

    # ------------------------------------------------------------------
    def query(self, search: str = "", min_level: str = "V", tag: str = "", limit: int = 500) -> list[dict]:
        """Filtered view of the buffer (newest last)."""
        order = LEVELS.index(min_level.upper()) if min_level.upper() in LEVELS else 0
        term = (search or "").lower()
        with self.lock:
            out = []
            for e in reversed(self.lines):
                lvl = e["level"]
                if lvl in LEVELS and LEVELS.index(lvl) < order:
                    continue
                if tag and tag.lower() not in e["tag"].lower():
                    continue
                if term and term not in e["message"].lower() and term not in e["tag"].lower():
                    continue
                out.append(e)
                if len(out) >= limit:
                    break
            out.reverse()
            return out

    def counts_by_level(self) -> dict:
        with self.lock:
            counts = {k: 0 for k in LEVELS}
            for e in self.lines:
                if e["level"] in counts:
                    counts[e["level"]] += 1
        return counts


def export_log(entries: list[dict], fmt: str = "txt", dest_dir: Path | None = None) -> Path:
    """Export captured logcat entries to TXT or JSON."""
    dest_dir = Path(dest_dir) if dest_dir else EXPORT_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = dest_dir / f"logcat_{stamp}.{fmt}"
    if fmt == "json":
        import json

        path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text("\n".join(e.get("raw", e.get("message", "")) for e in entries), encoding="utf-8")
    record_command("android.logcat_export", command=str(path), result="ok",
                   details={"lines": len(entries), "format": fmt})
    return path
