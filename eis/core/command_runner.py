"""Command execution helper for E.I.S. Core.

Wraps ``subprocess.run`` with:
- safety engine verification (blocks destructive patterns)
- timeout handling
- consistent result payload ``{"ok": bool, "stdout": str, "stderr": str, "returncode": int}``
- UTF-8 friendly decoding of Windows console output
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Sequence

from eis.core.safety import get_safety_engine

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
LONG_TIMEOUT = 120


class CommandResult(dict):
    """dict with attribute access for convenience."""

    def __getattr__(self, item: str):
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(item) from exc


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "cp437", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def run_command(
    command: Sequence[str] | str,
    timeout: int = DEFAULT_TIMEOUT,
    check_safety: bool = True,
    shell: bool = False,
    cwd: str | None = None,
    env_extra: dict | None = None,
) -> CommandResult:
    """Run *command*, capture output, never raise (errors go in the result)."""
    engine = get_safety_engine()
    text = command if isinstance(command, str) else subprocess.list2cmdline(list(command))

    if check_safety:
        verdict = engine.check_command(text)
        if not verdict.allowed:
            log.warning("Safety engine blocked command: %s", text)
            return CommandResult(
                ok=False,
                stdout="",
                stderr=verdict.confirmation_text or "Blocked by safety engine.",
                returncode=-1,
                blocked=True,
                level=verdict.level,
                command=text,
            )

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            shell=shell,
            cwd=cwd,
            env={**os.environ, **(env_extra or {})},
        )
        return CommandResult(
            ok=completed.returncode == 0,
            stdout=_decode(completed.stdout or b""),
            stderr=_decode(completed.stderr or b""),
            returncode=completed.returncode,
            command=text,
        )
    except subprocess.TimeoutExpired:
        log.warning("Command timed out after %ss: %s", timeout, text)
        return CommandResult(
            ok=False, stdout="", stderr=f"Timed out after {timeout}s.", returncode=-1,
            timeout=True, command=text,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            ok=False, stdout="", stderr=f"Executable not found: {exc}", returncode=-1,
            not_found=True, command=text,
        )
    except OSError as exc:
        return CommandResult(
            ok=False, stdout="", stderr=str(exc), returncode=-1, command=text,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return CommandResult(
            ok=False, stdout="", stderr=f"Unexpected error: {exc}", returncode=-1, command=text,
        )


def run_powershell(
    script: str,
    timeout: int = DEFAULT_TIMEOUT,
    check_safety: bool = True,
) -> CommandResult:
    """Run a PowerShell snippet safely (NoProfile, Bypass, no scope creep)."""
    argv = [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", script,
    ]
    return run_command(argv, timeout=timeout, check_safety=check_safety)


def run_cmd(command: str, timeout: int = DEFAULT_TIMEOUT, check_safety: bool = True) -> CommandResult:
    """Run a cmd.exe one-liner."""
    return run_command(["cmd", "/c", command], timeout=timeout, check_safety=check_safety)

