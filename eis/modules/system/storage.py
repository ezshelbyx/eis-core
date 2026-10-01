"""Storage analyzer and disk health (SMART) checker."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from eis.core.command_runner import run_command, run_powershell
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE, psutil

log = logging.getLogger(__name__)


def list_drives() -> list[dict[str, Any]]:
    """All mounted drives/partitions with capacity and filesystem info."""
    drives: list[dict[str, Any]] = []
    if PSUTIL_AVAILABLE:
        try:
            for part in psutil.disk_partitions(all=False):
                entry: dict[str, Any] = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype or "?",
                    "opts": part.opts,
                }
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    entry.update(
                        total=usage.total,
                        used=usage.used,
                        free=usage.free,
                        percent=usage.percent,
                    )
                except (PermissionError, OSError):
                    entry.update(total=0, used=0, free=0, percent=0.0, inaccessible=True)
                drives.append(entry)
            return drives
        except Exception as exc:  # pragma: no cover
            log.debug("psutil disk_partitions failed: %s", exc)
    # Fallback: PowerShell Get-PSDrive / Get-Volume
    if os.name == "nt":
        rows = _ps_json(
            "Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter,"
            "FileSystemLabel,FileSystem,@{n='Size';e={$_.Size}},@{n='SizeRemaining';e={$_.SizeRemaining}} | "
            "ConvertTo-Json -Compress"
        )
        for v in rows:
            total = _to_int(v.get("Size"))
            free = _to_int(v.get("SizeRemaining"))
            letter = v.get("DriveLetter", "")
            drives.append(
                {
                    "device": f"{letter}:" if letter else "?",
                    "mountpoint": f"{letter}:\\" if letter else "?",
                    "fstype": v.get("FileSystem", "?"),
                    "label": v.get("FileSystemLabel", ""),
                    "total": total,
                    "free": free,
                    "used": total - free,
                    "percent": round((total - free) / total * 100, 1) if total else 0.0,
                }
            )
    return drives


def disk_io_counters() -> dict:
    """Aggregate disk I/O since boot (for the dashboard sparkline)."""
    if not PSUTIL_AVAILABLE:
        return {}
    try:
        total = {"read_bytes": 0, "write_bytes": 0, "read_count": 0, "write_count": 0}
        for _, counters in (psutil.disk_io_counters(perdisk=True) or {}).items():
            total["read_bytes"] += counters.read_bytes
            total["write_bytes"] += counters.write_bytes
            total["read_count"] += counters.read_count
            total["write_count"] += counters.write_count
        return total
    except Exception:  # pragma: no cover
        return {}


def _ps_json(script: str, timeout: int = 15) -> list[dict]:
    res = run_powershell(script, timeout=timeout)
    if not res.ok or not res.stdout.strip():
        return []
    import json

    try:
        data = json.loads(res.stdout)
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, TypeError):
        return []


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Health / SMART
# ---------------------------------------------------------------------------

def disk_health(physical_drive: str = "") -> dict:
    """Windows storage health via Get-PhysicalDisk / Get-StorageReliabilityCounter.

    ``physical_drive`` may be a friendly name (e.g. ``"Samsung SSD 970"``);
    empty string checks the first disk.
    """
    result: dict[str, Any] = {
        "available": os.name == "nt",
        "drive": physical_drive or "(first disk)",
        "health_status": None,
        "temperature_c": None,
        "wear": None,
        "power_on_hours": None,
        "read_errors_total": None,
        "smart_ok": None,
        "raw": "",
    }
    if os.name != "nt":
        result["error"] = "Windows-only feature."
        return result

    filter_expr = ""
    if physical_drive:
        filter_expr = f"Where-Object FriendlyName -like '*{physical_drive}*'"
    rows = _ps_json(
        "Get-PhysicalDisk " + filter_expr + " | Select-Object FriendlyName,MediaType,"
        "HealthStatus,OperationalStatus,Size | ConvertTo-Json -Compress",
        timeout=20,
    )
    if rows:
        first = rows[0]
        result["drive"] = first.get("FriendlyName", result["drive"])
        result["health_status"] = first.get("HealthStatus")
        result["media_type"] = first.get("MediaType")
        result["size_gb"] = round(_to_int(first.get("Size")) / (1024 ** 3), 1)

    counters = _ps_json(
        "Get-PhysicalDisk " + filter_expr + " | Get-StorageReliabilityCounter | "
        "Select-Object Temperature,TemperatureMax,Wear,PowerOnHours,ReadErrorsTotal,"
        "ReadErrorsUncorrected,WriteErrorsTotal,WriteErrorsUncorrected | ConvertTo-Json -Compress",
        timeout=25,
    )
    if counters:
        c = counters[0]
        result["temperature_c"] = c.get("Temperature")
        result["wear"] = c.get("Wear")
        result["power_on_hours"] = c.get("PowerOnHours")
        result["read_errors_total"] = c.get("ReadErrorsTotal")
        result["write_errors_total"] = c.get("WriteErrorsTotal")

    result["smart_ok"] = (result["health_status"] or "").lower() in ("healthy", "warning") or result["health_status"] is None
    if result["health_status"] is None:
        # Fall back to wmic-style quick status.
        res = run_command(["cmd", "/c", "wmic diskdrive get status,model"], timeout=15, check_safety=False)
        result["raw"] = (res.stdout or "").strip()
        lines = [l for l in result["raw"].splitlines()[1:] if l.strip()]
        if lines:
            first = lines[0].strip()
            result["smart_ok"] = "ok" in first.lower()
            result["health_status"] = first
    return result


def health_summary() -> dict:
    """All physical disks, health-first view."""
    if os.name != "nt":
        return {"available": False, "disks": []}
    rows = _ps_json(
        "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,BusType,Size | ConvertTo-Json -Compress"
    )
    disks = []
    for r in rows:
        disks.append(
            {
                "name": r.get("FriendlyName", "?"),
                "media": r.get("MediaType", "?"),
                "bus": r.get("BusType", "?"),
                "health": r.get("HealthStatus", "?"),
                "size_gb": round(_to_int(r.get("Size")) / (1024 ** 3), 1),
            }
        )
    return {"available": True, "disks": disks}


def largest_files(root: str | Path, limit: int = 20) -> list[dict]:
    """Largest files under *root* (single-level scan, safe on low-end machines)."""
    root_path = Path(root)
    files: list[dict] = []
    try:
        for entry in root_path.rglob("*"):
            if entry.is_file():
                try:
                    files.append({"path": str(entry), "size": entry.stat().st_size})
                except OSError:
                    continue
            if len(files) > 20000:
                break
    except (OSError, PermissionError) as exc:
        log.debug("largest_files aborted: %s", exc)
    files.sort(key=lambda f: f["size"], reverse=True)
    return files[:limit]
