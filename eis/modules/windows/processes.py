"""Process manager: list, inspect and (with confirmation) end processes."""

from __future__ import annotations

import logging
import os

from eis.core.command_runner import run_command, run_powershell
from eis.core.paths import record_command
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE, psutil

log = logging.getLogger(__name__)


def list_processes(search: str = "", limit: int = 300) -> list[dict]:
    """Running processes with PID, CPU%, RAM, name and executable path."""
    procs: list[dict] = []
    if PSUTIL_AVAILABLE:
        for proc in psutil.process_iter(["pid", "name", "exe", "username", "cpu_percent", "memory_info", "status"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                procs.append(
                    {
                        "pid": info["pid"],
                        "name": info.get("name") or "?",
                        "exe": info.get("exe") or "",
                        "user": (info.get("username") or "").split("\\")[-1],
                        "cpu_percent": info.get("cpu_percent") or 0.0,
                        "ram_bytes": mem.rss if mem else 0,
                        "status": info.get("status") or "",
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    else:
        # Fallback via tasklist (CSV).
        res = run_command(["tasklist", "/FO", "CSV", "/NH"], timeout=25, check_safety=False)
        if res.ok:
            import csv
            import io

            reader = csv.reader(io.StringIO(res.stdout))
            for row in reader:
                if len(row) >= 5:
                    try:
                        mem_kb = int(row[4].replace(",", "").replace('"', "").replace(" K", ""))
                    except ValueError:
                        mem_kb = 0
                    procs.append(
                        {
                            "pid": int(row[1]) if row[1].isdigit() else 0,
                            "name": row[0].strip('"'),
                            "exe": "",
                            "user": "",
                            "cpu_percent": 0.0,
                            "ram_bytes": mem_kb * 1024,
                            "status": "",
                        }
                    )
    if search:
        term = search.lower()
        procs = [p for p in procs if term in p["name"].lower() or term in (p.get("exe") or "").lower()]
    procs.sort(key=lambda p: p.get("ram_bytes") or 0, reverse=True)
    return procs[:limit]


def process_details(pid: int) -> dict:
    """Deep details for one process (connections omitted for speed)."""
    if not PSUTIL_AVAILABLE:
        return {"ok": False, "error": "psutil required for process details."}
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            mem = proc.memory_info()
            cpu_times = proc.cpu_times()
            return {
                "ok": True,
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "cwd": _safe(lambda: proc.cwd()),
                "cmdline": " ".join(proc.cmdline() or []),
                "user": _safe(lambda: proc.username()),
                "status": proc.status(),
                "created": str(_safe(lambda: proc.create_time())),
                "cpu_percent": proc.cpu_percent(interval=0.1),
                "threads": proc.num_threads(),
                "ram_rss": mem.rss,
                "ram_vms": mem.vms,
                "cpu_user_time": cpu_times.user,
                "cpu_system_time": cpu_times.system,
            }
    except psutil.NoSuchProcess:
        return {"ok": False, "error": f"Process {pid} no longer exists."}
    except psutil.AccessDenied:
        return {"ok": False, "error": f"Access denied for process {pid} (try running as admin)."}


def _safe(func):
    try:
        return func()
    except Exception:
        return ""


def end_process(pid: int, confirm_executed: bool = False) -> dict:
    """Terminate a process.  The UI must ask for confirmation first."""
    if not confirm_executed:
        return {"ok": False, "error": "Confirmation required before ending a process."}
    record_command("process.end", command=f"taskkill /PID {pid}", result="requested")
    if PSUTIL_AVAILABLE:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
            record_command("process.end", command=f"terminate {name}", result="ok", details={"pid": pid})
            return {"ok": True, "pid": pid, "name": name}
        except psutil.NoSuchProcess:
            return {"ok": False, "error": f"Process {pid} no longer exists."}
        except psutil.AccessDenied:
            res = run_command(["taskkill", "/PID", str(pid), "/F"], timeout=15, check_safety=False)
            return {"ok": res.ok, "error": res.stderr, "pid": pid}
    res = run_command(["taskkill", "/PID", str(pid), "/F"], timeout=15, check_safety=False)
    record_command("process.end", command=f"taskkill /PID {pid}", result="ok" if res.ok else "error",
                   error=res.stderr, details={"pid": pid})
    return {"ok": res.ok, "error": res.stderr, "pid": pid}
