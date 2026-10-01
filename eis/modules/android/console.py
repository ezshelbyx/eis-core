"""ADB command center: safe presets + manual console with safety checks."""

from __future__ import annotations

import logging

from eis.core.command_runner import CommandResult, run_command
from eis.core.paths import record_command
from eis.core.safety import get_safety_engine
from eis.modules.android.adb import _run_adb, adb_path

log = logging.getLogger(__name__)

# Preset commands: (id, label, adb args, destructive, description)
PRESETS = [
    ("devices", "List devices", ["devices", "-l"], False, "Show connected devices and their state."),
    ("info", "Device info", ["shell", "getprop"], False, "Dump all system properties."),
    ("battery", "Battery status", ["shell", "dumpsys", "battery"], False, "Battery level, health and status."),
    ("storage", "Storage usage", ["shell", "df", "-h"], False, "Filesystem usage overview."),
    ("memory", "Memory info", ["shell", "cat", "/proc/meminfo"], False, "RAM usage information."),
    ("packages3rd", "List 3rd-party packages", ["shell", "pm", "list", "packages", "-3"], False, "User-installed packages."),
    ("wifilist", "Saved Wi-Fi networks", ["shell", "cmd", "wifi", "list-networks"], False, "Networks saved on the device."),
    ("screencap", "Screenshot to file", ["shell", "screencap", "-p", "/sdcard/eis_screenshot.png"], False,
     "Capture a screenshot to the device (then use Files > pull)."),
    ("wake", "Wake device", ["input", "keyevent", "KEYCODE_WAKEUP"], False, "Wake the screen."),
    ("reboot", "Reboot device", ["reboot"], True, "Reboots the phone."),
    ("recovery", "Reboot to recovery", ["reboot", "recovery"], True, "Reboots into recovery mode."),
]


def run_preset(preset_id: str, serial: str = "") -> dict:
    """Run one of the safe preset commands."""
    preset = next((p for p in PRESETS if p[0] == preset_id), None)
    if not preset:
        return {"ok": False, "error": f"Unknown preset: {preset_id}"}
    _pid, label, args, destructive, _desc = preset
    engine = get_safety_engine()
    if destructive:
        verdict = engine.check_command("adb " + " ".join(args))
        if not verdict.allowed:
            return {"ok": False, "error": verdict.confirmation_text}
    res = _run_adb(args, timeout=30, device=serial)
    record_command("android.preset", command=f"adb {' '.join(args)}",
                   result="ok" if res.ok else "error", error=res.stderr,
                   details={"preset": preset_id, "device": serial})
    return {
        "ok": res.ok,
        "preset": preset_id,
        "label": label,
        "command": f"adb {' '.join(args)}",
        "output": res.stdout or res.stderr,
        "confirm_required": destructive,
    }


def run_manual(command: str, serial: str = "", confirmed: bool = False) -> dict:
    """Run a raw adb command from the console after safety classification."""
    command = (command or "").strip()
    if not command:
        return {"ok": False, "error": "Empty command."}
    if not command.lower().startswith("adb"):
        command = f"adb {command}"
    # Split into argv (simple shlex; adb args rarely need POSIX quoting subtleties)
    import shlex

    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return {"ok": False, "error": f"Parse error: {exc}"}
    # Replace the 'adb' token with the resolved path
    if argv and argv[0].lower() == "adb":
        argv = argv[1:]
    if serial:
        argv = ["-s", serial] + argv

    engine = get_safety_engine()
    verdict = engine.check_command("adb " + " ".join(argv))
    if not verdict.allowed:
        record_command("android.manual", command=command, result="blocked")
        return {"ok": False, "error": verdict.confirmation_text, "blocked": True, "level": verdict.level}
    if verdict.requires_confirmation and not confirmed:
        return {
            "ok": False,
            "confirm_required": True,
            "level": verdict.level,
            "confirmation_text": verdict.confirmation_text or f"Run: {command}?",
            "command": command,
        }

    adb = adb_path()
    if not adb:
        return {"ok": False, "error": "ADB not found. Install Android platform-tools and set the path in Settings."}
    res = run_command([adb] + argv, timeout=60, check_safety=False)
    record_command("android.manual", command=command,
                   result="ok" if res.ok else "error", error=res.stderr if not res.ok else "")
    return {
        "ok": res.ok,
        "command": command,
        "output": res.stdout or res.stderr,
        "returncode": res.returncode,
    }
