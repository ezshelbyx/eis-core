"""ADB (Android Debug Bridge) detection and device management."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from eis.core.command_runner import CommandResult, run_command
from eis.core.paths import record_command
from eis.core.settings import get_settings

log = logging.getLogger(__name__)

_ADB_CANDIDATES = [
    "adb",
    r"C:\platform-tools\adb.exe",
    r"C:\adb\adb.exe",
    r"C:\Android\platform-tools\adb.exe",
]


def adb_path() -> str:
    """Resolve the ADB executable: settings override > PATH > common locations."""
    settings = get_settings()
    configured = (settings.get("android.adb_path") or "").strip()
    candidates = [configured] if configured else []
    candidates.extend(_ADB_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if resolved:
            return resolved
    return ""


def adb_available() -> bool:
    return bool(adb_path())


def _run_adb(args: list[str], timeout: int = 20, device: str = "") -> CommandResult:
    adb = adb_path()
    if not adb:
        return CommandResult(ok=False, stdout="", stderr="ADB not found. Install Android platform-tools.", returncode=-1, not_found=True)
    argv = [adb]
    if device:
        argv += ["-s", device]
    argv += args
    return run_command(argv, timeout=timeout, check_safety=False)


def is_adb_command(command: str) -> bool:
    """Cheap check used by the safety engine bridge."""
    return command.strip().lower().startswith("adb")


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def list_devices(mode: str = "adb") -> list[dict]:
    """Connected devices: mode='adb' (serials + state), mode='fastboot'."""
    if mode == "fastboot":
        return list_fastboot_devices()
    res = _run_adb(["devices", "-l"], timeout=15)
    devices = []
    if res.ok:
        for line in res.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append({"serial": parts[0], "state": parts[1], "info": " ".join(parts[2:])})
    return devices


def list_fastboot_devices() -> list[dict]:
    fb = fastboot_path()
    if not fb:
        return []
    res = run_command([fb, "devices"], timeout=15, check_safety=False)
    devices = []
    if res.ok:
        for line in res.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                devices.append({"serial": parts[0], "state": "fastboot" if parts[1] == "fastboot" else parts[1]})
    return devices


def fastboot_path() -> str:
    settings = get_settings()
    configured = (settings.get("android.fastboot_path") or "").strip()
    candidates = [configured] if configured else []
    candidates.append("fastboot")
    adb_dir = Path(adb_path()).parent if adb_path() else None
    if adb_dir:
        candidates.append(str(adb_dir / "fastboot.exe"))
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if resolved:
            return resolved
    return ""


def detect() -> dict:
    """Full detector payload for the Android section header."""
    adb = adb_path()
    return {
        "adb_found": bool(adb),
        "adb_path": adb,
        "fastboot_found": bool(fastboot_path()),
        "devices": list_devices(),
        "fastboot_devices": list_fastboot_devices(),
    }


# ---------------------------------------------------------------------------
# Device info
# ---------------------------------------------------------------------------

_INFO_PROPS = [
    ("model", "ro.product.model"),
    ("brand", "ro.product.brand"),
    ("manufacturer", "ro.product.manufacturer"),
    ("device", "ro.product.device"),
    ("android_version", "ro.build.version.release"),
    ("sdk", "ro.build.version.sdk"),
    ("build", "ro.build.display.id"),
    ("security_patch", "ro.build.version.security_patch"),
    ("serial", "ro.serialno"),
    ("cpu_abi", "ro.product.cpu.abi"),
    ("hardware", "ro.hardware"),
    ("board", "ro.product.board"),
    ("host", "ro.build.host"),
    ("kernel", "ro.kernel.version"),
]


def device_info(serial: str = "") -> dict:
    """Collect device properties via getprop."""
    res = _run_adb(["shell", "getprop"], timeout=25, device=serial)
    if not res.ok:
        return {"ok": False, "error": res.stderr or "Failed to read device properties (is USB debugging on?)",
                "authorized": "unauthorized" not in (res.stdout + res.stderr).lower()}
    props = {}
    for line in res.stdout.splitlines():
        if "]:" not in line:
            continue
        try:
            key, value = line.split("]: [", 1)
            key = key.strip().lstrip("[").strip()
            value = value.rstrip("]").strip()
            props[key] = value
        except ValueError:
            continue
    info = {"ok": True, "serial": serial or props.get("ro.serialno", ""), "raw": props}
    for field, prop in _INFO_PROPS:
        info[field] = props.get(prop, "")
    # Battery + storage quick facts
    batt = _run_adb(["shell", "dumpsys", "battery"], timeout=15, device=serial)
    if batt.ok:
        for line in batt.stdout.splitlines():
            if "level" in line.lower() and ":" in line:
                info["battery_level"] = line.split(":")[-1].strip()
            elif "status" in line.lower() and ":" in line:
                info["battery_status"] = line.split(":")[-1].strip()
    storage = _run_adb(["shell", "df", "-h", "/data"], timeout=15, device=serial)
    if storage.ok:
        for line in storage.stdout.splitlines():
            if "/data" in line and not line.startswith("Filesystem"):
                parts = line.split()
                if len(parts) >= 4:
                    info["data_total"] = parts[1]
                    info["data_used"] = parts[2]
                    info["data_free"] = parts[3]
                break
    return info


def quick_info(serial: str = "") -> dict:
    """Small subset used for the device list cards."""
    res = _run_adb(["shell", "getprop"], timeout=20, device=serial)
    if not res.ok:
        return {"ok": False, "error": res.stderr}
    wanted = {"ro.product.model": "model", "ro.product.brand": "brand", "ro.build.version.release": "android_version"}
    out = {"ok": True}
    for line in res.stdout.splitlines():
        if "]:" not in line:
            continue
        try:
            key, value = line.split("]: [", 1)
            key = key.strip().lstrip("[").strip()
            if key in wanted:
                out[wanted[key]] = value.rstrip("]").strip()
        except ValueError:
            continue
    return out
