"""Windows event log viewer (errors / warnings / critical) with filtering."""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_powershell

log = logging.getLogger(__name__)

LEVELS = {"critical": 1, "error": 2, "warning": 3, "information": 4}
COMMON_LOGS = ("System", "Application", "Security", "Setup")


def query_events(
    log_name: str = "System",
    level: str = "error",
    max_events: int = 50,
    source_filter: str = "",
    days: int = 7,
) -> dict:
    """Read recent events from *log_name* filtered by level.

    ``level`` may be one of LEVELS keys, or "all".
    """
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only.", "events": []}
    level_ids = []
    if level != "all":
        lid = LEVELS.get(level)
        if lid is None:
            return {"ok": False, "error": f"Unknown level: {level}", "events": []}
        level_ids = [lid]

    level_expr = ",".join(str(i) for i in level_ids) if level_ids else "1,2,3,4"
    since = f"(TimeCreated - gt (Get-Date).AddDays(-{int(days)}))"
    source_expr = ""
    if source_filter:
        source_expr = f" -and (ProviderName -like '*{source_filter}*')"

    script = (
        f"Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; Level={level_expr}; "
        f"StartTime=(Get-Date).AddDays(-{int(days)})}} -MaxEvents {int(max_events)} -ErrorAction SilentlyStop | "
        "Select-Object TimeCreated,LevelDisplayName,ProviderName,Id,Message | ConvertTo-Json -Compress -Depth 2"
    )
    res = run_powershell(script, timeout=45, check_safety=False)
    if not res.ok and "No events were found" not in res.stderr:
        return {"ok": False, "error": res.stderr or "Query failed.", "events": []}

    import json

    events = []
    if res.stdout.strip():
        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                message = str(row.get("Message") or "").replace("\r\n", " ").strip()
                events.append(
                    {
                        "time": str(row.get("TimeCreated", "")),
                        "level": row.get("LevelDisplayName") or str(row.get("Level", "")),
                        "source": row.get("ProviderName", ""),
                        "event_id": row.get("Id", ""),
                        "message": message[:300],
                    }
                )
        except (json.JSONDecodeError, TypeError) as exc:
            return {"ok": False, "error": f"Parse error: {exc}", "events": []}
    return {"ok": True, "log": log_name, "level": level, "count": len(events), "events": events}


def event_summary(days: int = 3) -> dict:
    """Counts of errors/warnings/critical across System and Application logs."""
    summary = {"ok": True, "period_days": days, "logs": {}}
    for log_name in ("System", "Application"):
        counts = {"critical": 0, "error": 0, "warning": 0}
        for level in counts:
            res = query_events(log_name=log_name, level=level, max_events=1, days=days)
            # max_events=1 returns at most 1; count via a separate measure query is slow.
            # We fetch a page and count here to keep it fast.
        # Real counts:
        script = (
            f"Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; Level=1,2,3; "
            f"StartTime=(Get-Date).AddDays(-{int(days)})}} -ErrorAction SilentlyContinue | "
            "Group-Object LevelDisplayName | Select-Object Name,Count | ConvertTo-Json -Compress"
        )
        res = run_powershell(script, timeout=45, check_safety=False)
        if res.ok and res.stdout.strip():
            import json

            try:
                data = json.loads(res.stdout)
                rows = data if isinstance(data, list) else [data]
                for row in rows:
                    name = (row.get("Name") or "").lower()
                    if "critical" in name:
                        counts["critical"] = int(row.get("Count", 0))
                    elif "error" in name:
                        counts["error"] = int(row.get("Count", 0))
                    elif "warning" in name:
                        counts["warning"] = int(row.get("Count", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        summary["logs"][log_name] = counts
    return summary


def open_event_viewer() -> dict:
    """Launch the built-in Event Viewer (safe shortcut)."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    os.startfile("eventvwr.msc")  # noqa: S606
    return {"ok": True, "opened": "eventvwr.msc"}
