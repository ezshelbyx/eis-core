"""Static system information collector (CPU, RAM, OS, BIOS, motherboard...)."""

from __future__ import annotations

import logging
import os
import platform
import socket
import time
from typing import Any

from eis.core.command_runner import run_powershell
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE, psutil

log = logging.getLogger(__name__)


def _win32(class_name: str, props: list[str]) -> list[dict]:
    """Query a WMI class via PowerShell CIM; returns list of dicts."""
    if os.name != "nt":
        return []
    prop_list = ", ".join(f'"{p}"' for p in props)
    script = (
        f"Get-CimInstance -ClassName {class_name} | "
        f"Select-Object {prop_list} | ConvertTo-Json -Compress -Depth 2"
    )
    res = run_powershell(script, timeout=15)
    if not res.ok or not res.stdout.strip():
        return []
    import json

    try:
        data = json.loads(res.stdout)
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, TypeError):
        return []


def _boot_time() -> float:
    if PSUTIL_AVAILABLE:
        try:
            return float(psutil.boot_time())
        except Exception:  # pragma: no cover
            pass
    if os.name == "nt":
        rows = _win32("Win32_OperatingSystem", ["LastBootUpTime"])
        if rows:
            raw = str(rows[0].get("LastBootUpTime", ""))
            try:
                from datetime import datetime

                return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                pass
    return 0.0


def uptime_seconds() -> float:
    boot = _boot_time()
    return max(0.0, time.time() - boot) if boot else 0.0


def collect(refresh_gpu: bool = True) -> dict[str, Any]:
    """Gather static system information.  Never raises; missing keys are 'Unknown'."""
    info: dict[str, Any] = {
        "hostname": socket.gethostname() if hasattr(socket, "gethostname") else "unknown",
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown",
        "python_version": platform.python_version(),
        "boot_time": _boot_time(),
        "uptime_seconds": uptime_seconds(),
        "is_admin": _is_admin_flag(),
    }

    if os.name == "nt":
        info["os_edition"] = _os_edition()
        info["os_build"] = _os_build()
        cpu_rows = _win32("Win32_Processor", ["Name", "NumberOfCores", "NumberOfLogicalProcessors", "MaxClockSpeed"])
        if cpu_rows:
            cpu = cpu_rows[0]
            info["cpu_name"] = cpu.get("Name", "Unknown")
            info["cpu_cores"] = cpu.get("NumberOfCores", "?")
            info["cpu_threads"] = cpu.get("NumberOfLogicalProcessors", "?")
            info["cpu_max_clock_mhz"] = cpu.get("MaxClockSpeed", 0)
        board_rows = _win32("Win32_BaseBoard", ["Manufacturer", "Product", "SerialNumber"])
        if board_rows:
            b = board_rows[0]
            info["motherboard"] = f"{b.get('Manufacturer', '?')} {b.get('Product', '?')}".strip()
            info["motherboard_serial"] = b.get("SerialNumber", "")
        bios_rows = _win32("Win32_BIOS", ["Manufacturer", "SMBIOSBIOSVersion", "ReleaseDate"])
        if bios_rows:
            b = bios_rows[0]
            info["bios_vendor"] = b.get("Manufacturer", "Unknown")
            info["bios_version"] = b.get("SMBIOSBIOSVersion", "Unknown")
            info["bios_release"] = str(b.get("ReleaseDate", "") or "Unknown")[:10]
        info["ram_total_gb"] = _ram_total_gb()
        if refresh_gpu:
            info["gpus"] = _gpu_list()
    return info


def _is_admin_flag() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name == "nt" else os.geteuid() == 0
    except Exception:
        return False


def _os_edition() -> str:
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            name, _ = winreg.QueryValueEx(key, "ProductName")
            return str(name)
    except Exception:
        return platform.release() or "Windows"


def _os_build() -> str:
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
            ubr = 0
            try:
                ubr, _ = winreg.QueryValueEx(key, "UBR")
            except OSError:
                pass
            display, _ = winreg.QueryValueEx(key, "DisplayVersion") if True else ("", None)
            return f"{build}.{ubr} ({display})"
    except Exception:
        return platform.version() or "Unknown"


def _ram_total_gb() -> float:
    if PSUTIL_AVAILABLE:
        try:
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            pass
    rows = _win32("Win32_ComputerSystem", ["TotalPhysicalMemory"])
    if rows:
        try:
            return round(int(rows[0].get("TotalPhysicalMemory", 0)) / (1024 ** 3), 1)
        except (TypeError, ValueError):
            pass
    return 0.0


def _gpu_list() -> list[str]:
    rows = _win32("Win32_VideoController", ["Name", "AdapterRAM", "DriverVersion"])
    gpus = []
    for r in rows:
        name = r.get("Name", "Unknown GPU")
        vram = r.get("AdapterRAM") or 0
        try:
            vram_mb = int(vram) // (1024 * 1024)
        except (TypeError, ValueError):
            vram_mb = 0
        gpus.append(f"{name} ({vram_mb} MB, driver {r.get('DriverVersion', '?')})" if vram_mb else name)
    return gpus
