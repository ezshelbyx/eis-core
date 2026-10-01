"""Hardware scanner: enumerates connected devices and their specifications."""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_powershell
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE, psutil

log = logging.getLogger(__name__)


def _ps_json(script: str, timeout: int = 20) -> list[dict]:
    res = run_powershell(script, timeout=timeout)
    if not res.ok or not res.stdout.strip():
        return []
    import json

    try:
        data = json.loads(res.stdout)
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, TypeError):
        return []


def scan(summary_only: bool = False) -> dict:
    """Scan hardware categories.  Returns ``{"categories": {...}, "errors": [...]}``."""
    result: dict = {"categories": {}, "errors": []}

    # --- CPU ------------------------------------------------------------
    cpus = _ps_json(
        "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
        "NumberOfLogicalProcessors,MaxClockSpeed,LoadPercentage | ConvertTo-Json -Compress"
    )
    result["categories"]["cpu"] = [
        {
            "name": c.get("Name", "Unknown"),
            "cores": c.get("NumberOfCores", "?"),
            "threads": c.get("NumberOfLogicalProcessors", "?"),
            "max_clock_mhz": c.get("MaxClockSpeed", 0),
        }
        for c in cpus
    ] or ([{"name": psutil.cpu_info()[0]["name"] if psutil.cpu_info() else platform_processor()}] if PSUTIL_AVAILABLE else [])

    # --- RAM modules -----------------------------------------------------
    mem = _ps_json(
        "Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,PartNumber,"
        "Capacity,Speed,ConfiguredClockSpeed,DeviceLocator | ConvertTo-Json -Compress"
    )
    result["categories"]["memory"] = [
        {
            "slot": m.get("DeviceLocator", "?"),
            "manufacturer": (m.get("Manufacturer", "") or "").strip() or "Unknown",
            "part_number": (m.get("PartNumber", "") or "").strip(),
            "capacity_gb": round(_to_int(m.get("Capacity")) / (1024 ** 3), 1) if m.get("Capacity") else 0,
            "speed_mhz": _to_int(m.get("ConfiguredClockSpeed") or m.get("Speed")),
        }
        for m in mem
    ]

    # --- Motherboard / BIOS ----------------------------------------------
    board = _ps_json(
        "Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version | ConvertTo-Json -Compress"
    )
    result["categories"]["motherboard"] = [
        {"manufacturer": b.get("Manufacturer", "?"), "product": b.get("Product", "?"), "version": b.get("Version", "")}
        for b in board
    ]
    bios = _ps_json(
        "Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,SerialNumber | ConvertTo-Json -Compress"
    )
    result["categories"]["bios"] = [
        {"vendor": b.get("Manufacturer", "?"), "version": b.get("SMBIOSBIOSVersion", "?"), "serial": b.get("SerialNumber", "")}
        for b in bios
    ]

    # --- Storage ----------------------------------------------------------
    disks = _ps_json(
        "Get-CimInstance Win32_DiskDrive | Select-Object Model,Size,InterfaceType,"
        "MediaType,SerialNumber | ConvertTo-Json -Compress"
    )
    result["categories"]["storage"] = [
        {
            "model": d.get("Model", "?"),
            "size_gb": round(_to_int(d.get("Size")) / (1024 ** 3), 1) if d.get("Size") else 0,
            "interface": d.get("InterfaceType", "?"),
            "type": d.get("MediaType", "?"),
            "serial": d.get("SerialNumber", ""),
        }
        for d in disks
    ]

    # --- GPUs -------------------------------------------------------------
    gpus = _ps_json(
        "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,"
        "VideoModeDescription | ConvertTo-Json -Compress"
    )
    result["categories"]["graphics"] = [
        {
            "name": g.get("Name", "?"),
            "vram_mb": round(_to_int(g.get("AdapterRAM")) / (1024 ** 2), 0) if g.get("AdapterRAM") else 0,
            "driver": g.get("DriverVersion", "?"),
            "mode": g.get("VideoModeDescription", ""),
        }
        for g in gpus
    ]

    # --- Audio / Network adapters (summary only when asked) ----------------
    if not summary_only:
        net = _ps_json(
            "Get-NetAdapter | Select-Object Name,InterfaceDescription,MacAddress,LinkSpeed | ConvertTo-Json -Compress"
        )
        result["categories"]["network_adapters"] = [
            {
                "name": n.get("Name", "?"),
                "description": n.get("InterfaceDescription", "?"),
                "mac": n.get("MacAddress", ""),
                "link_speed": n.get("LinkSpeed", ""),
            }
            for n in net
        ]
        audio = _ps_json(
            "Get-CimInstance Win32_SoundDevice | Select-Object Name,Manufacturer | ConvertTo-Json -Compress"
        )
        result["categories"]["audio"] = [
            {"name": a.get("Name", "?"), "manufacturer": a.get("Manufacturer", "")} for a in audio
        ]

    # --- PnP problem devices (driver issues) -------------------------------
    problems = _ps_json(
        "Get-PnpDevice | Where-Object { $_.Status -ne 'OK' } | Select-Object FriendlyName,Class,Status | ConvertTo-Json -Compress",
        timeout=30,
    )
    result["problem_devices"] = [
        {"name": p.get("FriendlyName", "?"), "class": p.get("Class", ""), "status": p.get("Status", "?")}
        for p in problems
    ][:50]

    return result


def platform_processor() -> str:
    import platform

    return platform.processor() or "Unknown"


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
