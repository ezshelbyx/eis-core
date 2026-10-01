"""Android package manager: list, enable/disable/uninstall (with confirmation)."""

from __future__ import annotations

import logging
import re

from eis.core.paths import record_command
from eis.modules.android.adb import _run_adb

log = logging.getLogger(__name__)


def list_packages(serial: str = "", kind: str = "3rd", search: str = "") -> dict:
    """List packages: kind = '3rd' (user), 'system', 'all' or 'enabled'/'disabled'."""
    args_map = {
        "3rd": ["shell", "pm", "list", "packages", "-3"],
        "system": ["shell", "pm", "list", "packages", "-s"],
        "all": ["shell", "pm", "list", "packages"],
        "enabled": ["shell", "pm", "list", "packages", "-e"],
        "disabled": ["shell", "pm", "list", "packages", "-d"],
    }
    args = args_map.get(kind, args_map["3rd"])
    res = _run_adb(args, timeout=30, device=serial)
    if not res.ok:
        return {"ok": False, "error": res.stderr or "pm list failed", "packages": []}
    packages = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            name = line[len("package:"):]
            if search and search.lower() not in name.lower():
                continue
            packages.append(name)
    packages.sort()
    return {"ok": True, "kind": kind, "count": len(packages), "packages": packages}


def package_info(package: str, serial: str = "") -> dict:
    """Details for one package via dumpsys (version, permissions)."""
    res = _run_adb(["shell", "dumpsys", "package", package], timeout=25, device=serial)
    if not res.ok:
        return {"ok": False, "error": res.stderr or "dumpsys failed"}
    text = res.stdout
    info: dict = {"ok": True, "package": package}
    m = re.search(r"versionName=([\w.\-]+)", text)
    if m:
        info["version"] = m.group(1)
    m = re.search(r"versionCode=(\d+)", text)
    if m:
        info["version_code"] = m.group(1)
    m = re.search(r"targetSdk=(\d+)", text)
    if m:
        info["target_sdk"] = m.group(1)
    m = re.search(r"minSdk=(\d+)", text)
    if m:
        info["min_sdk"] = m.group(1)
    perms = sorted(set(re.findall(r"android\.permission\.[A-Z_]+", text)))
    info["permissions"] = perms
    info["permission_count"] = len(perms)
    m = re.search(r"firstInstallTime=([\d\-: ]+)", text)
    if m:
        info["installed_at"] = m.group(1).strip()
    m = re.search(r"lastUpdateTime=([\d\-: ]+)", text)
    if m:
        info["updated_at"] = m.group(1).strip()
    info["enabled"] = "disabled=true" not in text
    return info


def change_package_state(package: str, action: str, serial: str = "", confirmed: bool = False) -> dict:
    """Enable/disable/uninstall/clear-data a package.  Confirmation required."""
    actions = {
        "enable": (["shell", "pm", "enable", package], False),
        "disable": (["shell", "pm", "disable-user", "--user", "0", package], True),
        "uninstall": (["shell", "pm", "uninstall", "-k", "--user", "0", package], True),
        "clear_data": (["shell", "pm", "clear", package], True),
    }
    if action not in actions:
        return {"ok": False, "error": f"Unsupported action: {action}"}
    args, destructive = actions[action]
    if destructive and not confirmed:
        return {
            "ok": False,
            "confirm_required": True,
            "command": f"adb {' '.join(args)}",
            "warning": (
                f"This will {action} '{package}' for user 0. "
                "The system keeps the APK (uninstall keeps data with -k)."
            ),
        }
    res = _run_adb(args, timeout=40, device=serial)
    record_command("android.package", command=f"adb {' '.join(args)}",
                   result="ok" if res.ok else "error", error=res.stderr if not res.ok else "",
                   details={"package": package, "device": serial})
    return {"ok": res.ok, "package": package, "action": action,
            "output": (res.stdout or res.stderr).strip()}
