"""Windows repair center: SFC and DISM operations (elevated, logged, confirmed)."""

from __future__ import annotations

import logging
from typing import Callable

from eis.core.command_runner import run_powershell
from eis.core.paths import record_command
from eis.core.privilege import is_admin, run_elevated

log = logging.getLogger(__name__)

# Operations that are safe to expose.  Keys are stable identifiers used by the UI.
SFC_OPERATIONS = {
    "scan": ("SFC /SCANNOW", "Verify and repair all protected system files (takes 5-20 min)."),
    "verify": ("SFC /VERIFYONLY", "Verify system files without repairing (read-only)."),
    "scanfile": ("SFC /SCANFILE=<file>", "Verify and repair one specific file."),
}

DISM_OPERATIONS = {
    "checkhealth": ("DISM /Online /Cleanup-Image /CheckHealth", "Quick flag check (seconds)."),
    "scanhealth": ("DISM /Online /Cleanup-Image /ScanHealth", "Deep corruption scan (10-30 min)."),
    "restorehealth": ("DISM /Online /Cleanup-Image /RestoreHealth", "Repair the component store (10-40 min)."),
}


def _log_dir():
    from eis.core.logging_config import LOG_DIR

    return LOG_DIR / "sfc_dism"


def run_sfc(operation: str = "scan", extra_arg: str = "", progress: Callable[[str], None] | None = None) -> dict:
    """Run an SFC operation elevated and return parsed results.

    The command runs in an elevated cmd.exe window; output is captured to a
    temp file and also written to ``data/logs/sfc_dism/``.
    """
    cmd_text, _ = SFC_OPERATIONS.get(operation, SFC_OPERATIONS["scan"])
    command = cmd_text.replace("<file>", extra_arg) if "<file>" in cmd_text else cmd_text
    if not command.upper().startswith("SFC"):
        return {"ok": False, "error": "Unknown SFC operation."}

    if not is_admin():
        record_command("windows.sfc", command=command, result="elevation-required")
        elevated = run_elevated_cmd(command)
        return {
            "ok": elevated.get("ok", False),
            "operation": operation,
            "command": command,
            "elevated": True,
            "output": elevated.get("stdout", ""),
            "error": elevated.get("error", ""),
            "log_file": elevated.get("log_file"),
            "needs_elevation": not elevated.get("ok", False),
        }

    res = run_powershell(f"cmd /c {command}", timeout=1800)
    output = res.stdout + res.stderr
    log_file = _save_log("sfc", operation, command, output, res.returncode if hasattr(res, 'returncode') else -1)
    record_command("windows.sfc", command=command, result="ok" if res.ok else "error", error=res.stderr)
    return {
        "ok": res.ok,
        "operation": operation,
        "command": command,
        "output": output,
        "log_file": str(log_file) if log_file else None,
        "integrity_violations": _parse_sfc_output(output),
    }


def run_dism(operation: str = "checkhealth", progress: Callable[[str], None] | None = None) -> dict:
    """Run a DISM operation elevated and return results."""
    cmd_text, description = DISM_OPERATIONS.get(operation, DISM_OPERATIONS["checkhealth"])
    if not is_admin():
        record_command("windows.dism", command=cmd_text, result="elevation-required")
        elevated = run_elevated_cmd(cmd_text)
        return {
            "ok": elevated.get("ok", False),
            "operation": operation,
            "command": cmd_text,
            "description": description,
            "elevated": True,
            "output": elevated.get("stdout", ""),
            "error": elevated.get("error", ""),
            "log_file": elevated.get("log_file"),
            "needs_elevation": not elevated.get("ok", False),
        }

    res = run_powershell(f"cmd /c {cmd_text}", timeout=3600)
    output = res.stdout + res.stderr
    log_file = _save_log("dism", operation, cmd_text, output, res.returncode if hasattr(res, 'returncode') else -1)
    record_command("windows.dism", command=cmd_text, result="ok" if res.ok else "error", error=res.stderr)
    return {
        "ok": res.ok,
        "operation": operation,
        "command": cmd_text,
        "description": description,
        "output": output,
        "log_file": str(log_file) if log_file else None,
    }


def run_elevated_cmd(command: str, timeout: int = 3600) -> dict:
    """Run a cmd.exe command elevated, capturing output to a log file."""
    result = run_elevated(["cmd", "/c", command], timeout=timeout)
    log_file = None
    if result.get("stdout"):
        log_file = _save_log("elevated", "cmd", command, result["stdout"], result.get("returncode", -1))
        result["log_file"] = str(log_file)
    return result


def _save_log(tool: str, operation: str, command: str, output: str, returncode: int):
    """Persist repair output under data/logs/sfc_dism/."""
    try:
        from datetime import datetime

        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = log_dir / f"{tool}_{operation}_{stamp}.log"
        path.write_text(
            f"# {tool.upper()} {operation}\n# {command}\n# returncode={returncode}\n\n{output}\n",
            encoding="utf-8",
        )
        return path
    except OSError as exc:  # pragma: no cover
        log.warning("Could not save repair log: %s", exc)
        return None


def _parse_sfc_output(output: str) -> str:
    """Extract the interesting verdict line from SFC output."""
    for marker in (
        "did not find any integrity violations",
        "found corrupt files and successfully repaired them",
        "found corrupt files but was unable to fix",
    ):
        if marker in output.lower():
            return marker
    return ""
