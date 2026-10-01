"""Windows services manager (inspect + safe start/stop with confirmation)."""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_powershell
from eis.core.paths import record_command
from eis.core.privilege import is_admin

log = logging.getLogger(__name__)


def list_services(search: str = "", running_only: bool = False, limit: int = 400) -> list[dict]:
    """Services with status, startup type, name and description."""
    script = (
        "Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode,"
        "ProcessId,StartName,PathName,Description | ConvertTo-Json -Compress -Depth 2"
    )
    res = run_powershell(script, timeout=40, check_safety=False)
    services: list[dict] = []
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                desc = str(row.get("Description") or "").replace("\r\n", " ")
                services.append(
                    {
                        "name": row.get("Name", ""),
                        "display_name": row.get("DisplayName", ""),
                        "status": row.get("State", ""),
                        "startup_type": row.get("StartMode", ""),
                        "pid": row.get("ProcessId", 0),
                        "account": row.get("StartName", ""),
                        "path": row.get("PathName", ""),
                        "description": desc[:200],
                    }
                )
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning("services parse error: %s", exc)
    if running_only:
        services = [s for s in services if s["status"] == "Running"]
    if search:
        term = search.lower()
        services = [
            s for s in services
            if term in s["name"].lower() or term in s["display_name"].lower()
            or term in s["description"].lower()
        ]
    return services[:limit]


def service_details(name: str) -> dict:
    res = run_powershell(
        f"Get-CimInstance Win32_Service -Filter \"Name='{name}'\" | "
        "Select-Object Name,DisplayName,State,StartMode,ProcessId,StartName,PathName,"
        "Description,DelayedAutoStart | ConvertTo-Json -Compress",
        timeout=15, check_safety=False,
    )
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            row = data[0] if isinstance(data, list) else data
            row["ok"] = True
            return row
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    return {"ok": False, "error": res.stderr or f"Service '{name}' not found."}


def change_service_state(name: str, action: str, confirm_executed: bool = False) -> dict:
    """Start/Stop/Restart a service.  Confirmation + elevation required."""
    if not confirm_executed:
        return {"ok": False, "error": f"Confirmation required before {action} on service '{name}'."}
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "error": f"Unsupported action: {action}"}
    verb = {"start": "Start-Service", "stop": "Stop-Service -Force", "restart": "Restart-Service -Force"}[action]
    script = f"{verb} -Name '{name}' -ErrorAction Stop; 'OK'"
    if is_admin():
        res = run_powershell(script, timeout=60, check_safety=False)
        ok = res.ok and "OK" in res.stdout
    else:
        from eis.core.privilege import run_elevated

        elevated = run_elevated(["powershell", "-NoProfile", "-Command", script], timeout=120)
        ok = elevated.get("ok", False)
    record_command("windows.service", command=f"{action} {name}", result="ok" if ok else "error")
    return {"ok": ok, "service": name, "action": action}


def open_services_console() -> dict:
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    os.startfile("services.msc")  # noqa: S606
    return {"ok": True, "opened": "services.msc"}
