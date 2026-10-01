"""Live CPU and memory monitors for the E.I.S. Core dashboard."""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_powershell
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE, psutil
from eis.modules.system.system_info import uptime_seconds

log = logging.getLogger(__name__)


def cpu_stats(interval: float = 0.35) -> dict:
    """Current CPU usage, per-core usage, frequency and temperature."""
    data: dict = {
        "available": PSUTIL_AVAILABLE,
        "percent_total": None,
        "percent_per_core": [],
        "freq_mhz": None,
        "temp_c": None,
        "cores": os.cpu_count() or 0,
        "threads": os.cpu_count() or 0,
    }
    if PSUTIL_AVAILABLE:
        try:
            data["percent_total"] = psutil.cpu_percent(interval=interval)
            data["percent_per_core"] = psutil.cpu_percent(interval=0, percpu=True)
            freq = psutil.cpu_freq()
            if freq:
                data["freq_mhz"] = round(freq.current or 0, 0)
                data["freq_min_mhz"] = round(freq.min or 0, 0)
                data["freq_max_mhz"] = round(freq.max or 0, 0)
            temps = _read_temps()
            if temps:
                data["temp_c"] = temps
        except Exception as exc:  # pragma: no cover - defensive
            log.debug("cpu_stats psutil error: %s", exc)
    else:
        # Fallback: single WMIC sample without psutil.
        if os.name == "nt":
            res = run_powershell(
                "Get-CimInstance Win32_Processor | Select-Object -First 1 "
                "LoadPercentage | ConvertTo-Json -Compress",
                timeout=8,
            )
            if res.ok and res.stdout.strip():
                try:
                    import json

                    d = json.loads(res.stdout)
                    data["percent_total"] = float(d.get("LoadPercentage") or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
    return data


def _read_temps() -> float | None:
    """Best-effort CPU temperature (psutil sensors + MSAcpi_ThermalZoneTemperature)."""
    if PSUTIL_AVAILABLE:
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            for entries in temps.values():
                for entry in entries:
                    if entry.current:
                        return round(float(entry.current), 1)
        except Exception:
            pass
    if os.name == "nt":
        res = run_powershell(
            "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction Stop | Select-Object -First 1 CurrentTemperature | "
            "ConvertTo-Json -Compress",
            timeout=6,
        )
        if res.ok and res.stdout.strip():
            try:
                import json

                d = json.loads(res.stdout)
                # Tenths of degrees Kelvin.
                return round((float(d["CurrentTemperature"]) / 10.0) - 273.15, 1)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                pass
    return None


def ram_stats() -> dict:
    """Memory + swap snapshot."""
    data: dict = {
        "available": PSUTIL_AVAILABLE,
        "total": 0,
        "used": 0,
        "available_bytes": 0,
        "percent": 0.0,
        "swap_total": 0,
        "swap_used": 0,
        "swap_percent": 0.0,
    }
    if PSUTIL_AVAILABLE:
        try:
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            data.update(
                total=vm.total,
                used=vm.used,
                available_bytes=vm.available,
                percent=vm.percent,
                swap_total=sm.total,
                swap_used=sm.used,
                swap_percent=sm.percent,
            )
            return data
        except Exception as exc:  # pragma: no cover
            log.debug("ram_stats psutil error: %s", exc)
    if os.name == "nt":
        res = run_powershell(
            "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,"
            "FreePhysicalMemory,SizeStoredInPagingFiles,FreeSpaceInPagingFiles | ConvertTo-Json -Compress",
            timeout=8,
        )
        if res.ok and res.stdout.strip():
            try:
                import json

                d = json.loads(res.stdout)
                total_kb = float(d.get("TotalVisibleMemorySize") or 0)
                free_kb = float(d.get("FreePhysicalMemory") or 0)
                swap_total_kb = float(d.get("SizeStoredInPagingFiles") or 0)
                swap_free_kb = float(d.get("FreeSpaceInPagingFiles") or 0)
                data.update(
                    total=int(total_kb * 1024),
                    available_bytes=int(free_kb * 1024),
                    used=int((total_kb - free_kb) * 1024),
                    percent=round((total_kb - free_kb) / total_kb * 100, 1) if total_kb else 0.0,
                    swap_total=int(swap_total_kb * 1024),
                    swap_used=int((swap_total_kb - swap_free_kb) * 1024),
                    swap_percent=round((swap_total_kb - swap_free_kb) / swap_total_kb * 100, 1) if swap_total_kb else 0.0,
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    return data


def uptime_summary() -> dict:
    secs = uptime_seconds()
    days, rem = divmod(int(secs), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return {
        "seconds": secs,
        "human": f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m",
        "boot_time": None,
    }
