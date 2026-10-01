"""Windows version / edition / architecture / build detection."""

from __future__ import annotations

import logging
import os
import platform
import sys

log = logging.getLogger(__name__)

_KNOWN_RELEASES = {
    "26100": "Windows 11 24H2",
    "22631": "Windows 11 23H2",
    "22621": "Windows 11 22H2",
    "22000": "Windows 11 21H2",
    "19045": "Windows 10 22H2",
    "19044": "Windows 10 21H2",
    "19043": "Windows 10 21H1",
    "19042": "Windows 10 20H2",
    "19041": "Windows 10 2004",
    "18363": "Windows 10 1909",
    "18362": "Windows 10 1903",
    "17763": "Windows 10 1809",
    "17134": "Windows 10 1803",
    "16299": "Windows 10 1709",
    "15063": "Windows 10 1703",
    "14393": "Windows 10 1607",
}

_REG_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"


def detect() -> dict:
    """Full Windows identity payload.  Works cross-platform (degrades)."""
    is64 = sys.maxsize > 2 ** 32
    info: dict = {
        "family": platform.system() or "Unknown",
        "is_windows": os.name == "nt",
        "version": platform.version(),
        "release": platform.release(),
        "architecture": platform.machine() or ("x64" if is64 else "x86"),
        "python_arch": platform.architecture()[0],
    }
    if os.name != "nt":
        info["edition"] = info["family"]
        info["build"] = info["release"]
        info["build_full"] = info["release"]
        info["display_version"] = ""
        info["release_name"] = ""
        info["pretty"] = platform.platform()
        info["install_date"] = ""
        info["registered_owner"] = ""
        info["edition_id"] = ""
        return info

    info["edition"] = _winreg_read("ProductName", platform.release() or "Windows")
    info["edition_id"] = _winreg_read("EditionID")
    build = _winreg_read("CurrentBuildNumber", platform.version())
    ubr = _winreg_read("UBR", "0")
    info["build"] = build
    info["build_full"] = f"{build}.{ubr}" if ubr else build
    info["display_version"] = _winreg_read("DisplayVersion") or _winreg_read("ReleaseId")
    info["registered_owner"] = _winreg_read("RegisteredOwner")
    info["install_date"] = _install_date(_winreg_read("InstallDate", "0"))
    info["build_lab"] = _winreg_read("BuildLabEx")
    info["release_name"] = _KNOWN_RELEASES.get(build, info["display_version"] or "Unknown release")
    info["pretty"] = (
        f"{info['edition']} - Build {info['build_full']} ({info['release_name']})"
    ).strip()
    return info


def _winreg_read(name: str, default: str = "") -> str:
    """Read one HKLM value from CurrentVersion."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REG_PATH) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return default


def _install_date(raw: str) -> str:
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(raw), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError, OverflowError):
        return ""
