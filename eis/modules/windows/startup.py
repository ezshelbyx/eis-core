"""Startup manager: apps configured to launch with Windows."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from eis.core.command_runner import run_powershell

log = logging.getLogger(__name__)

if os.name == "nt":
    import winreg  # type: ignore

    _RUN_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM", winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM (32)", winreg.KEY_READ),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKCU", winreg.KEY_READ),
    ]


def list_startup() -> list[dict]:
    """Startup entries from Run keys, RunOnce keys and Startup folders."""
    entries: list[dict] = []
    if os.name != "nt":
        return entries

    # --- Registry Run / RunOnce ------------------------------------------
    for hive, path, label, access in _RUN_KEYS:
        entries.extend(_read_run_key(hive, path, label, access, once=False))
        once_path = path.replace("\\Run", "\\RunOnce")
        entries.extend(_read_run_key(hive, once_path, label, access, once=True))

    # --- Startup folders ---------------------------------------------------
    for folder in _startup_folders():
        try:
            for item in Path(folder).glob("*"):
                if item.is_file():
                    entries.append(
                        {
                            "name": item.stem,
                            "command": str(item),
                            "location": f"Startup folder: {folder}",
                            "once": False,
                        }
                    )
        except OSError:
            continue

    # --- Scheduled tasks at logon (read-only summary) -----------------------
    entries.extend(_logon_tasks())

    return entries


def _read_run_key(hive, path: str, label: str, access: int, once: bool) -> list[dict]:
    out = []
    try:
        with winreg.OpenKey(hive, path, 0, access) as key:
            index = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, index)
                    index += 1
                except OSError:
                    break
                out.append(
                    {
                        "name": name,
                        "command": str(value),
                        "location": f"Registry: {label}\\...\\{'RunOnce' if once else 'Run'}",
                        "once": once,
                    }
                )
    except OSError:
        pass
    return out


def _startup_folders() -> list[str]:
    import os as _os

    common = _os.environ.get("ProgramData", r"C:\ProgramData")
    user = _os.environ.get("APPDATA", "")
    return [
        rf"{common}\Microsoft\Windows\Start Menu\Programs\StartUp",
        rf"{user}\Microsoft\Windows\Start Menu\Programs\Startup",
    ]


def _logon_tasks() -> list[dict]:
    """Scheduled tasks triggered at logon (read-only, informational)."""
    res = run_powershell(
        "Get-ScheduledTask | Where-Object { $_.Triggers.CimClass.CimClassName -contains 'MSFT_TaskLogonTrigger' -and $_.State -ne 'Disabled' } | "
        "Select-Object -First 40 TaskName,TaskPath,State | ConvertTo-Json -Compress",
        timeout=25,
        check_safety=False,
    )
    if not res.ok or not res.stdout.strip():
        return []
    import json

    try:
        data = json.loads(res.stdout)
        rows = data if isinstance(data, list) else [data]
        return [
            {
                "name": f"{t.get('TaskPath', '').strip(chr(92))}{t.get('TaskName', '')}",
                "command": "(scheduled task at logon)",
                "location": "Task Scheduler (logon trigger)",
                "once": False,
            }
            for t in rows
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def open_startup_settings() -> dict:
    """Open Windows' own Startup Apps settings (safe, user-controlled)."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    os.startfile("ms-settings:startupapps")  # noqa: S606 - opens Settings app
    return {"ok": True, "opened": "ms-settings:startupapps"}
