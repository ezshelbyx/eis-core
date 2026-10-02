"""Tests for the command runner."""

from __future__ import annotations

import sys

import pytest

from eis.core.command_runner import run_command, run_powershell


def test_successful_command():
    res = run_command([sys.executable, "--version"])
    assert res.ok
    assert res.returncode == 0
    assert "Python" in res.stdout


def test_failing_command_reports_error():
    res = run_command([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert not res.ok
    assert res.returncode == 3


def test_missing_executable():
    res = run_command(["definitely-not-a-real-binary-xyz"])
    assert not res.ok
    assert res.not_found


def test_timeout():
    res = run_command([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    assert not res.ok
    assert res.timeout


def test_safety_blocks_destructive():
    res = run_command("format C:", check_safety=True, shell=True)
    assert not res.ok
    assert res.blocked


def test_safety_bypass_for_internal_reads():
    # Internal modules bypass the safety engine for read-only lookups.
    res = run_command([sys.executable, "--version"], check_safety=False)
    assert res.ok


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_powershell_runs():
    # PowerShell cold start (first .NET assembly load) can exceed 20s on
    # low-end HDD machines, so use a generous timeout here.
    res = run_powershell("Write-Output 'eis-test-ok'", timeout=90)
    assert res.ok
    assert "eis-test-ok" in res.stdout
