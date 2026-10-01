"""Installed applications manager (registry-based, search + uninstall shortcut)."""

from __future__ import annotations

import logging
import os

from eis.core.paths import record_command

log = logging.getLogger(__name__)

if os.name == "nt":
    import winreg  # type: ignore

    _UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ),
    ]


def list_installed() -> list[dict]:
    """Installed applications from the classic Uninstall registry keys."""
    apps: dict[str, dict] = {}
    if os.name != "nt":
        return []
    for hive, path, access in _UNINSTALL_KEYS:
        try:
            hive_handle = winreg.OpenKey(hive, path, 0, access)
        except OSError:
            continue
        with hive_handle:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(hive_handle, index)
                    index += 1
                except OSError:
                    break
                try:
                    with winreg.OpenKey(hive_handle, subkey_name, 0, access) as subkey:
                        app = _read_app(subkey)
                        if app and app.get("name"):
                            apps[app["name"].lower()] = app
                except OSError:
                    continue
    return sorted(apps.values(), key=lambda a: a["name"].lower())


def _read_app(subkey) -> dict | None:
    def q(name: str) -> str:
        try:
            value, _ = winreg.QueryValueEx(subkey, name)
            return str(value) if value is not None else ""
        except OSError:
            return ""

    name = q("DisplayName")
    if not name or q("SystemComponent") == "1":
        return None
    if q("ParentKeyName"):
        return None  # update entries, not standalone apps
    return {
        "name": name,
        "version": q("DisplayVersion"),
        "publisher": q("Publisher"),
        "install_date": q("InstallDate"),
        "estimated_size_mb": _size_mb(q("EstimatedSize")),
        "install_location": q("InstallLocation"),
        "uninstall_string": q("UninstallString"),
        "quiet_uninstall": q("QuietUninstallString"),
        "registry_key": subkey.__class__ and "" or "",  # placeholder, set below
    }


def _size_mb(raw: str) -> int:
    try:
        return int(raw) // 1024 if raw else 0
    except ValueError:
        return 0


def search_installed(term: str, apps: list[dict] | None = None) -> list[dict]:
    apps = apps if apps is not None else list_installed()
    term = term.strip().lower()
    if not term:
        return apps
    return [
        a for a in apps
        if term in a["name"].lower()
        or term in (a.get("publisher") or "").lower()
        or term in (a.get("version") or "").lower()
    ]


def build_uninstall_command(app: dict) -> str | None:
    """Return the app's own uninstall command (user-visible before execution)."""
    return app.get("uninstall_string") or None
