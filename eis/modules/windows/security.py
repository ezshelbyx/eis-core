"""Security centers: Windows Firewall and Defender status (inspection only).

This module NEVER disables security features.  It exposes status and opens the
corresponding management consoles for the user.
"""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_powershell
from eis.core.paths import record_command
from eis.core.privilege import is_admin

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------

def firewall_status() -> dict:
    """Firewall state for Domain/Private/Public profiles."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only.", "profiles": {}}
    res = run_powershell(
        "Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,"
        "DefaultOutboundAction,AllowInboundRules | ConvertTo-Json -Compress",
        timeout=20, check_safety=False,
    )
    profiles = {}
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                profiles[row.get("Name", "?").lower()] = {
                    "enabled": row.get("Enabled"),
                    "inbound": row.get("DefaultInboundAction"),
                    "outbound": row.get("DefaultOutboundAction"),
                }
        except (json.JSONDecodeError, TypeError):
            pass
    active = _active_profile()
    return {"ok": bool(profiles), "profiles": profiles, "active_profile": active, "error": res.stderr}


def _active_profile() -> str:
    res = run_powershell(
        "(Get-NetConnectionProfile | Select-Object -First 1 NetworkCategory).NetworkCategory",
        timeout=10, check_safety=False,
    )
    return res.stdout.strip() if res.ok else ""


def firewall_rules_count() -> dict:
    res = run_powershell(
        "(Get-NetFirewallRule | Measure-Object).Count", timeout=30, check_safety=False
    )
    try:
        return {"ok": res.ok, "count": int(res.stdout.strip() or 0)}
    except ValueError:
        return {"ok": False, "count": None}


def open_firewall_console() -> dict:
    """Open Windows Defender Firewall with Advanced Security (user-controlled)."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    os.startfile("wf.msc")  # noqa: S606
    record_command("windows.firewall", command="open wf.msc", result="ok")
    return {"ok": True, "opened": "wf.msc"}


# ---------------------------------------------------------------------------
# Defender
# ---------------------------------------------------------------------------

def defender_status() -> dict:
    """Defender status payload.  Never modifies protection."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    res = run_powershell(
        "Get-MpComputerStatus | Select-Object AMServiceEnabled,AntispywareEnabled,"
        "AntivirusEnabled,RealTimeProtectionEnabled,BehaviorMonitorEnabled,"
        "AntivirusSignatureLastUpdated,QuickScanStartTime,FullScanStartTime,"
        "TamperProtectionSource,IsTamperProtected | ConvertTo-Json -Compress",
        timeout=25, check_safety=False,
    )
    if not res.ok or not res.stdout.strip():
        return {"ok": False, "error": res.stderr or "Get-MpComputerStatus unavailable.", "status": {}}
    import json

    try:
        data = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": "Parse error.", "status": {}}
    status = {
        "antivirus_enabled": bool(data.get("AntivirusEnabled")),
        "real_time_enabled": bool(data.get("RealTimeProtectionEnabled")),
        "antispyware_enabled": bool(data.get("AntispywareEnabled")),
        "behavior_monitor": bool(data.get("BehaviorMonitorEnabled")),
        "tamper_protected": bool(data.get("IsTamperProtected")),
        "signature_updated": str(data.get("AntivirusSignatureLastUpdated") or ""),
        "last_quick_scan": str(data.get("QuickScanStartTime") or ""),
        "last_full_scan": str(data.get("FullScanStartTime") or ""),
    }
    threats = _defender_threats()
    return {"ok": True, "status": status, "threats": threats}


def _defender_threats() -> list[dict]:
    res = run_powershell(
        "Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -First 10 "
        "InitialDetectionTime,ProcessName,Resources | ConvertTo-Json -Compress",
        timeout=20, check_safety=False,
    )
    if not res.ok or not res.stdout.strip():
        return []
    import json

    try:
        data = json.loads(res.stdout)
        rows = data if isinstance(data, list) else [data]
        return [
            {
                "time": str(t.get("InitialDetectionTime", "")),
                "process": str(t.get("ProcessName", "")),
                "resources": str(t.get("Resources", ""))[:200],
            }
            for t in rows
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def start_defender_scan(scan_type: str = "quick", confirm_executed: bool = False) -> dict:
    """Start a Defender scan (quick/full).  Never disables anything."""
    if not confirm_executed:
        return {"ok": False, "error": "Confirmation required before starting a scan."}
    if scan_type not in ("quick", "full"):
        return {"ok": False, "error": "Scan type must be quick or full."}
    cmdlet = "Start-MpScan -ScanType QuickScan" if scan_type == "quick" else "Start-MpScan -ScanType FullScan"
    if is_admin():
        res = run_powershell(cmdlet, timeout=60, check_safety=False)
        ok = res.ok
    else:
        from eis.core.privilege import run_elevated

        elevated = run_elevated(["powershell", "-NoProfile", "-Command", cmdlet], timeout=120)
        ok = elevated.get("ok", False)
    record_command("windows.defender_scan", command=cmdlet, result="ok" if ok else "error")
    return {"ok": ok, "scan": scan_type, "note": "Scan runs in the background; check Windows Security for progress."}


def open_windows_security() -> dict:
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    os.startfile("windowsdefender:")  # noqa: S606
    return {"ok": True, "opened": "Windows Security"}


# ---------------------------------------------------------------------------
# System restore
# ---------------------------------------------------------------------------

def restore_point_status() -> dict:
    """Check System Restore availability and existing restore points."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    res = run_powershell(
        "Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Sort-Object CreationTime -Descending | "
        "Select-Object -First 10 SequenceNumber,Description,CreationTime,RestorePointType | ConvertTo-Json -Compress",
        timeout=25, check_safety=False,
    )
    points = []
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            points = [
                {
                    "seq": p.get("SequenceNumber"),
                    "description": p.get("Description", ""),
                    "time": str(p.get("CreationTime", "")),
                    "type": str(p.get("RestorePointType", "")),
                }
                for p in rows
            ]
        except (json.JSONDecodeError, TypeError):
            pass
    enabled_res = run_powershell(
        "Get-CimInstance -ClassName Win32_SystemRestoreConfiguration -ErrorAction SilentlyContinue | "
        "Select-Object RPSessionInterval | ConvertTo-Json -Compress",
        timeout=15, check_safety=False,
    )
    return {"ok": True, "points": points, "count": len(points)}


def create_restore_point(description: str = "E.I.S. Core checkpoint", confirm_executed: bool = False) -> dict:
    """Create a system restore point (elevation + explicit confirmation)."""
    if not confirm_executed:
        return {"ok": False, "error": "Confirmation required before creating a restore point."}
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    script = (
        f"Checkpoint-Computer -Description '{description[:80]}' -RestorePointType MODIFY_SETTINGS; $?"
    )
    if is_admin():
        res = run_powershell(script, timeout=180, check_safety=False)
        ok = res.ok and "True" in res.stdout
        output = res.stdout + res.stderr
    else:
        from eis.core.privilege import run_elevated

        elevated = run_elevated(["powershell", "-NoProfile", "-Command", script], timeout=240)
        ok = elevated.get("ok", False)
        output = elevated.get("stdout", "") + elevated.get("error", "")
    record_command("windows.restore_point", command=script, result="ok" if ok else "error")
    return {
        "ok": ok,
        "output": output.strip(),
        "note": "Windows limits restore-point creation to once per 24h unless configured otherwise.",
    }
