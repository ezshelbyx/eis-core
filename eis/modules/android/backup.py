"""Android backup assistant: pull APKs, files and accessible data."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from eis.core.command_runner import run_command
from eis.core.logging_config import DOWNLOAD_DIR
from eis.core.paths import record_command
from eis.core.utils import format_bytes
from eis.modules.android.adb import _run_adb, adb_path

log = logging.getLogger(__name__)


def list_installed_apk_paths(serial: str = "", third_party_only: bool = True) -> list[dict]:
    """Map package names to APK paths on the device."""
    args = ["shell", "pm", "list", "packages", "-f"]
    if third_party_only:
        args.append("-3")
    res = _run_adb(args, timeout=40, device=serial)
    if not res.ok:
        return []
    apps = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        body = line[len("package:"):]
        if "=" in body:
            apk_path, package = body.rsplit("=", 1)
            apps.append({"package": package, "apk_path": apk_path})
    apps.sort(key=lambda a: a["package"])
    return apps


def backup_apk(package: str, serial: str = "", dest_dir: Path | None = None) -> dict:
    """Pull one APK from the device to data/downloads/apk/<package>/."""
    if not adb_path():
        return {"ok": False, "error": "ADB not found."}
    locate = _run_adb(["shell", "pm", "path", package], timeout=20, device=serial)
    if not locate.ok:
        return {"ok": False, "error": locate.stderr or f"Package not found: {package}"}
    apk_device_path = locate.stdout.strip().splitlines()[0]
    if apk_device_path.startswith("package:"):
        apk_device_path = apk_device_path[len("package:"):]
    dest_dir = Path(dest_dir) if dest_dir else DOWNLOAD_DIR / "apk" / package
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{package}.apk"
    res = _run_adb(["pull", apk_device_path, str(dest_file)], timeout=120, device=serial)
    record_command("android.backup_apk", command=f"adb pull {apk_device_path}",
                   result="ok" if res.ok else "error", error=res.stderr if not res.ok else "",
                   details={"package": package})
    if res.ok and dest_file.exists():
        return {"ok": True, "package": package, "file": str(dest_file),
                "size": format_bytes(dest_file.stat().st_size)}
    return {"ok": False, "error": res.stderr or "Pull failed."}


def pull_file(device_path: str, serial: str = "", dest_dir: Path | None = None) -> dict:
    """Pull a file or folder from the device (user-accessible paths)."""
    if not device_path.strip():
        return {"ok": False, "error": "Device path required."}
    dest_dir = Path(dest_dir) if dest_dir else DOWNLOAD_DIR / "device" / datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir.mkdir(parents=True, exist_ok=True)
    res = _run_adb(["pull", device_path, str(dest_dir)], timeout=300, device=serial)
    record_command("android.pull", command=f"adb pull {device_path}",
                   result="ok" if res.ok else "error", error=res.stderr if not res.ok else "")
    if res.ok:
        pulled = list(dest_dir.rglob("*"))
        size = sum(f.stat().st_size for f in pulled if f.is_file())
        return {"ok": True, "device_path": device_path, "dest": str(dest_dir),
                "files": len(pulled), "size": format_bytes(size), "output": res.stdout.strip()}
    return {"ok": False, "error": res.stderr or "Pull failed.", "output": res.stdout}


def push_file(local_path: str, device_path: str, serial: str = "", confirmed: bool = False) -> dict:
    """Push a local file to the device (requires confirmation - writes to device)."""
    if not confirmed:
        return {"ok": False, "confirm_required": True,
                "warning": f"Copy {local_path} to device at {device_path}?"}
    src = Path(local_path)
    if not src.is_file():
        return {"ok": False, "error": f"Local file not found: {src}"}
    res = _run_adb(["push", str(src), device_path], timeout=300, device=serial)
    record_command("android.push", command=f"adb push {src} {device_path}",
                   result="ok" if res.ok else "error")
    return {"ok": res.ok, "output": (res.stdout or res.stderr).strip()}


def backup_user_data_summary(serial: str = "") -> dict:
    """Inventory what can reasonably be backed up without root."""
    res = _run_adb(["shell", "ls", "/sdcard/"], timeout=20, device=serial)
    folders = []
    if res.ok:
        for line in res.stdout.splitlines():
            name = line.strip().rstrip("/:")
            if name and not name.startswith("Permission"):
                folders.append(name)
    known = [f for f in ("DCIM", "Download", "Documents", "Music", "Pictures", "Movies", "Recordings", "Android") if f in folders]
    return {
        "ok": res.ok,
        "accessible_folders": folders[:40],
        "recommended": known,
        "note": "Without root, backup covers /sdcard media/files and installed APKs.",
    }
