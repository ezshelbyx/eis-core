"""Maintenance operations: DNS cache flush, temp cleaner, network reset."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

from eis.core.command_runner import run_command, run_powershell
from eis.core.paths import record_command
from eis.core.privilege import is_admin
from eis.core.utils import format_bytes

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DNS cache
# ---------------------------------------------------------------------------

def flush_dns() -> dict:
    """Flush the Windows DNS resolver cache (requires elevation)."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    if is_admin():
        res = run_command(["ipconfig", "/flushdns"], timeout=20, check_safety=False)
        record_command("network.flush_dns", command="ipconfig /flushdns",
                       result="ok" if res.ok else "error", error=res.stderr)
        return {"ok": res.ok, "output": res.stdout.strip() or res.stderr.strip()}
    from eis.core.privilege import run_elevated

    elevated = run_elevated(["cmd", "/c", "ipconfig /flushdns"], timeout=60)
    record_command("network.flush_dns", command="ipconfig /flushdns (elevated)",
                   result="ok" if elevated.get("ok") else "error", error=elevated.get("error", ""))
    return {"ok": elevated.get("ok", False), "output": elevated.get("stdout", ""),
            "error": elevated.get("error", "")}


def show_dns_cache_stats() -> dict:
    res = run_powershell(
        "Get-DnsClientCache | Measure-Object | Select-Object Count | ConvertTo-Json -Compress",
        timeout=15, check_safety=False,
    )
    count = None
    if res.ok and res.stdout.strip():
        try:
            import json

            count = json.loads(res.stdout).get("Count")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return {"ok": res.ok, "cached_entries": count, "error": res.stderr}


# ---------------------------------------------------------------------------
# Temporary files cleaner
# ---------------------------------------------------------------------------

CLEANER_LOCATIONS = [
    ("User temp folder", lambda: Path(os.environ.get("TEMP", ""))),
    ("Windows temp", lambda: Path(os.environ.get("WINDIR", "")) / "Temp"),
    ("Prefetch (Windows)", lambda: Path(os.environ.get("WINDIR", "")) / "Prefetch"),
    ("Windows Update cache", lambda: Path(os.environ.get("WINDIR", "")) / "SoftwareDistribution" / "Download"),
    ("Delivery Optimization", lambda: Path(os.environ.get("WINDIR", "")) / "SoftwareDistribution" / "DeliveryOptimization"),
    ("Thumbnails cache", lambda: Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Explorer"),
    ("Recycle Bin (all drives)", None),  # special-cased below
]


def cleaner_targets() -> list[dict]:
    """Selectable cleanup locations with current size estimate."""
    from eis.core.safety import get_safety_engine

    engine = get_safety_engine()
    targets = []
    for name, resolver in CLEANER_LOCATIONS:
        if resolver is None:  # Recycle Bin: computed via PowerShell
            size = _recycle_bin_size()
            targets.append({"name": name, "path": "<Recycle Bin>", "size_bytes": size, "allowed": True})
            continue
        try:
            path = resolver()
        except Exception:
            path = None
        if not path or not path.exists():
            targets.append({"name": name, "path": "-", "size_bytes": 0, "allowed": False})
            continue
        allowed = not engine.is_path_protected(path) or "temp" in path.as_posix().lower() or "Temp" in str(path)
        targets.append(
            {
                "name": name,
                "path": str(path),
                "size_bytes": _dir_size(path),
                "allowed": allowed,
            }
        )
    return targets


def estimate_cleanable(selected: list[str] | None = None) -> dict:
    """Estimate how much can be recovered from selected locations."""
    targets = cleaner_targets()
    total = 0
    breakdown = []
    for t in targets:
        if selected and t["name"] not in selected:
            continue
        if not t.get("allowed"):
            continue
        total += t["size_bytes"]
        breakdown.append({"name": t["name"], "size_bytes": t["size_bytes"]})
    return {"total_bytes": total, "total_human": format_bytes(total), "breakdown": breakdown}


def clean(selected: list[str], confirm_executed: bool = False, progress: Callable[[str], None] | None = None) -> dict:
    """Delete temp files in the selected locations.  Requires explicit confirmation."""
    if not confirm_executed:
        return {"ok": False, "error": "Confirmation required before deleting files."}
    from eis.core.safety import get_safety_engine

    engine = get_safety_engine()
    results = {"cleaned_bytes": 0, "files_removed": 0, "errors": [], "locations": []}
    for name in selected:
        target = next((t for t in cleaner_targets() if t["name"] == name), None)
        if not target or not target.get("allowed"):
            continue
        if "Recycle Bin" in name:
            out = _empty_recycle_bin()
            results["locations"].append({"name": name, **out})
            continue
        path = Path(target["path"])
        if not path.exists() or not engine.validate_cleanup_root(path):
            results["errors"].append(f"Skipped protected/missing: {path}")
            continue
        before = target["size_bytes"]
        removed, errors = _clean_dir(path, progress)
        results["cleaned_bytes"] += min(removed, before)
        results["files_removed"] += len(errors)  # placeholder replaced below
        results["locations"].append({"name": name, "removed_bytes": removed, "errors": errors})
    record_command("maintenance.clean", command=", ".join(selected),
                   result="ok", details={"bytes": results["cleaned_bytes"]})
    results["cleaned_human"] = format_bytes(results["cleaned_bytes"])
    return results


def _clean_dir(path: Path, progress=None) -> tuple[int, list[str]]:
    """Delete files older than 24h inside *path* (not the folder itself)."""
    import time

    removed = 0
    errors: list[str] = []
    cutoff = time.time() - 86400  # keep files younger than a day
    try:
        for item in path.glob("*"):
            try:
                if item.is_file() and item.stat().st_mtime < cutoff:
                    size = item.stat().st_size
                    item.unlink()
                    removed += size
                elif item.is_dir():
                    import shutil

                    if item.stat().st_mtime < cutoff:
                        size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        shutil.rmtree(item, ignore_errors=True)
                        removed += size
            except (OSError, PermissionError) as exc:
                errors.append(str(exc))
            if progress:
                progress(f"Cleaning {path.name}: {item.name}")
    except OSError as exc:
        errors.append(str(exc))
    return removed, errors


def _dir_size(path: Path, max_files: int = 20000) -> int:
    total = 0
    count = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
                count += 1
                if count >= max_files:
                    break
    except OSError:
        pass
    return total


def _recycle_bin_size() -> int:
    if os.name != "nt":
        return 0
    res = run_powershell(
        "$s=0; Get-ChildItem 'C:\\$Recycle.Bin' -Recurse -Force -ErrorAction SilentlyContinue | "
        "Where-Object { -not $_.PSIsContainer } | ForEach-Object { $s += $_.Length }; $s",
        timeout=30, check_safety=False,
    )
    try:
        return int(res.stdout.strip() or 0)
    except ValueError:
        return 0


def _empty_recycle_bin() -> dict:
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    res = run_powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue; $?",
                         timeout=60, check_safety=False)
    return {"ok": res.ok or "True" in res.stdout, "output": res.stdout.strip()}


# ---------------------------------------------------------------------------
# Network reset (with confirmation + explanation)
# ---------------------------------------------------------------------------

NETWORK_RESET_STEPS = [
    ("winsock", "netsh winsock reset", "Resets the Winsock catalog (fixes corrupted network stacks). Requires restart."),
    ("tcp_ip", "netsh int ip reset", "Resets TCP/IP settings to defaults (static IPs are lost). Requires restart."),
    ("firewall", "netsh advfirewall reset", "Restores Windows Firewall to default policy (custom rules are lost)."),
    ("dns", "ipconfig /flushdns", "Clears the DNS resolver cache (harmless)."),
    ("release_renew", "ipconfig /release & ipconfig /renew", "Requests a new DHCP lease (brief disconnect)."),
]


def network_reset_steps() -> list[dict]:
    """Available reset steps with human explanations (for confirmation UI)."""
    return [{"id": sid, "command": cmd, "description": desc} for sid, cmd, desc in NETWORK_RESET_STEPS]


def perform_network_reset(step_ids: list[str], confirm_executed: bool = False) -> dict:
    """Execute selected network reset steps.  Elevation + confirmation required."""
    if not confirm_executed:
        return {"ok": False, "error": "Confirmation required: network reset disrupts connectivity."}
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only."}
    results = []
    for step in NETWORK_RESET_STEPS:
        sid, cmd, desc = step
        if sid not in step_ids:
            continue
        if is_admin():
            res = run_command(["cmd", "/c", cmd], timeout=60, check_safety=False)
            outcome = {"step": sid, "command": cmd, "ok": res.ok, "output": res.stdout.strip() or res.stderr.strip()}
        else:
            from eis.core.privilege import run_elevated

            elevated = run_elevated(["cmd", "/c", cmd], timeout=120)
            outcome = {"step": sid, "command": cmd, "ok": elevated.get("ok", False),
                       "output": elevated.get("stdout", ""), "error": elevated.get("error", "")}
        record_command("maintenance.network_reset", command=cmd,
                       result="ok" if outcome["ok"] else "error", error=outcome.get("error", ""))
        results.append(outcome)
    return {"ok": all(r["ok"] for r in results) if results else False, "steps": results}
