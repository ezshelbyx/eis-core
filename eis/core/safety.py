"""Safety engine for E.I.S. Core.

Central policy for destructive/privileged actions:
- classifies commands (read-only / state-changing / destructive / blocked)
- enforces confirmation requirements
- protects critical system directories from cleaners and duplicate finders
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Command classification
# --------------------------------------------------------------------------

STATE_TOKENS = (
    "set ", "add ", "new ", "start ", "stop ", "enable", "disable",
    "install", "uninstall", "flush", "reset", "create", "delete", "del ",
    "remove", "clear", "kill", "sc config", "sc start", "sc stop",
    "pm enable", "pm disable", "settings put", "launch", "boot",
    "sfc /scannow", "sfc /scanfile", "sfc /verifyfile", "sfc /verifyonly",
    "dism /online /cleanup-image", "dism /restorehealth",
)

DESTRUCTIVE_TOKENS = (
    "del ", "rmdir", "rd ", "erase", "format", "diskpart", "cipher /w",
    "reg delete", "reg add", "reg import", "reg restore",
    "vssadmin delete", "wbadmin delete", "bcdedit /delete",
    "pnputil /delete-driver", "netsh advfirewall reset",
    "net user ", "net localgroup ",
    "shutdown", "taskkill", "stop-process", "remove-item",
    "clear-content", "remove-itemproperty", "clear-dnsclientcache",
    "ipconfig /flushdns", "ipconfig /release", "ipconfig /renew",
    "adb uninstall", "pm uninstall", "pm disable", "pm enable",
    "adb reboot", "adb shell rm ", "adb shell settings put",
    "fastboot erase", "fastboot format", "fastboot flash", "fastboot oem",
    "fastboot flashing unlock", "fastboot flashing lock",
    "eventlog", "clear-eventlog", "wevtutil cl",
)

BLOCKED_PATTERNS = [
    r"format\s+[a-z]:",
    r"\bdel\s+/[sfq]", r"\berase\s+/[sfq]",
    r"\brd\s+/s", r"\brmdir\s+/s",
    r"cipher\s+/w\b",
    r"vssadmin\s+delete\s+shadows\s+/all",
    r"\bdiskpart\b",
    r"reg\s+delete\s+.{0,20}\bhkey_local_machine\s*\bsam\b",
    r"\bshutdown\b",
    r"stop-computer", r"restart-computer",
    r"mkfs", r"\bdd\s+if=",
    r"adb shell\s+.*\bsu\b",
    r"adb\s+reboot\s+(bootloader|recovery)",
    r"adb shell rm\s+/(\s|$)",
    r"fastboot\s+flashing\s+unlock",
    r"fastboot\s+oem\s+unlock",
    r"fastboot\s+flash\s+boot",
]


@dataclass
class SafetyVerdict:
    allowed: bool
    level: str                    # "read" | "state" | "destructive" | "blocked"
    requires_confirmation: bool = False
    reason: str = ""
    confirmation_text: str = ""


class SafetyEngine:
    """Evaluate commands/paths before execution.  Fail closed by default."""

    def __init__(self, settings=None):
        from eis.core.settings import get_settings

        self.settings = settings or get_settings()

    # -- commands ----------------------------------------------------------
    def classify_command(self, command: str) -> SafetyVerdict:
        cmd = (command or "").strip()
        low = cmd.lower()

        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, low):
                return SafetyVerdict(
                    allowed=False,
                    level="blocked",
                    reason=f"Blocked pattern matched: {pattern}",
                    confirmation_text=(
                        "This command is blocked by the E.I.S. safety engine "
                        "(destructive to the system or device)."
                    ),
                )

        level = "read"
        for token in DESTRUCTIVE_TOKENS:
            if token in low:
                level = "destructive"
                break
        if level == "read":
            for token in STATE_TOKENS:
                if token in low:
                    level = "state"
                    break

        destructive = level == "destructive"
        requires_confirmation = self.settings.get("safety.require_confirmation", True) and (
            destructive or level == "state"
        )
        text = ""
        if destructive:
            text = (
                "This action changes or deletes data and may be hard to undo.\n"
                f"Command: {cmd}\n\nDo you want to continue?"
            )
        elif level == "state":
            text = f"This action changes system/device state.\nCommand: {cmd}\n\nContinue?"
        return SafetyVerdict(
            allowed=True,
            level=level,
            requires_confirmation=requires_confirmation,
            reason="",
            confirmation_text=text,
        )

    def check_command(self, command: str) -> SafetyVerdict:
        """Alias kept for readability at call sites."""
        return self.classify_command(command)

    # -- paths -------------------------------------------------------------
    def protected_directories(self) -> list[Path]:
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        profile = Path(os.environ.get("USERPROFILE", "C:/Users/user"))
        return [
            windir,
            windir / "System32",
            windir / "SysWOW64",
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
            Path(os.environ.get("ProgramData", "C:/ProgramData")),
            profile / "Documents",
            profile / "Desktop",
            profile / "Pictures",
            profile / "AppData",
        ]

    def is_path_protected(self, path: Path | str) -> bool:
        """True when *path* resolves inside a protected directory."""
        try:
            p = Path(str(path)).resolve()
        except (OSError, ValueError):
            return True  # unresolvable -> treat as protected (fail closed)
        if p == Path(p.anchor or "C:/"):
            return True  # drive root
        for guard in self.protected_directories():
            try:
                if p == guard or p.is_relative_to(guard):
                    return True
            except (OSError, ValueError):
                continue
        return False

    def validate_cleanup_root(self, root: Path) -> bool:
        """True when a cleaner may operate inside *root*."""
        if self.settings.get("safety.block_system_dirs", True):
            return not self.is_path_protected(root)
        return not self.is_path_protected(root)

    def guard_scan_root(self, root: Path | str) -> tuple[bool, str]:
        """Validate a user-chosen scan/delete root; return (ok, reason)."""
        r = Path(str(root))
        if not r.exists():
            return False, "Path does not exist."
        if self.settings.get("safety.block_system_dirs", True) and self.is_path_protected(r):
            return False, (
                "Refusing to operate inside a protected system/user directory "
                "(see Settings → Safety)."
            )
        return True, ""


# --------------------------------------------------------------------------
# Singleton
# --------------------------------------------------------------------------

_engine: SafetyEngine | None = None


def get_safety_engine() -> SafetyEngine:
    global _engine
    if _engine is None:
        _engine = SafetyEngine()
    return _engine
