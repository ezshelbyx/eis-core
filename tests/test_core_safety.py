"""Tests for the safety engine."""

from __future__ import annotations

from pathlib import Path

from eis.core.safety import SafetyEngine


class TestCommandClassification:
    def test_read_only_allowed(self, safety_engine: SafetyEngine):
        verdict = safety_engine.check_command("tasklist /v")
        assert verdict.allowed
        assert verdict.level == "read"
        assert not verdict.requires_confirmation

    def test_destructive_requires_confirmation(self, safety_engine: SafetyEngine):
        verdict = safety_engine.check_command("taskkill /PID 4242")
        assert verdict.allowed
        assert verdict.level == "destructive"
        assert verdict.requires_confirmation

    def test_format_blocked(self, safety_engine: SafetyEngine):
        verdict = safety_engine.check_command("format C: /q")
        assert not verdict.allowed
        assert verdict.level == "blocked"

    def test_diskpart_blocked(self, safety_engine: SafetyEngine):
        verdict = safety_engine.check_command("diskpart")
        assert not verdict.allowed

    def test_shutdown_blocked(self, safety_engine: SafetyEngine):
        for cmd in ("shutdown /s /t 0", "shutdown -r"):
            assert not safety_engine.check_command(cmd).allowed

    def test_fastboot_unlock_blocked(self, safety_engine: SafetyEngine):
        assert not safety_engine.check_command("fastboot flashing unlock").allowed

    def test_adb_root_blocked(self, safety_engine: SafetyEngine):
        assert not safety_engine.check_command("adb shell su").allowed

    def test_sfc_requires_confirmation(self, safety_engine: SafetyEngine):
        verdict = safety_engine.check_command("sfc /scannow")
        assert verdict.allowed
        assert verdict.requires_confirmation

    def test_del_recursive_blocked(self, safety_engine: SafetyEngine):
        assert not safety_engine.check_command("del /s /q C:\\Users").allowed


class TestPathProtection:
    def test_windows_dir_protected(self, safety_engine: SafetyEngine, tmp_path: Path):
        import os

        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        assert safety_engine.is_path_protected(windir)

    def test_drive_root_protected(self, safety_engine: SafetyEngine):
        assert safety_engine.is_path_protected("C:/")

    def test_never_refuses_temp_like_outside(self, safety_engine: Path):
        # A plain project subdir is not protected
        from eis.core.logging_config import PROJECT_ROOT

        assert not safety_engine.is_path_protected(PROJECT_ROOT / "data")

    def test_guard_scan_root_rejects_missing(self, safety_engine: SafetyEngine, tmp_path: Path):
        ok, reason = safety_engine.guard_scan_root(tmp_path / "does-not-exist")
        assert not ok
        assert reason
