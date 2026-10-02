"""Tests for Android modules (no device required - parsing + safety gates)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from eis.modules.android.console import PRESETS, run_manual
from eis.modules.android.logcat import LogcatBuffer


class TestAdbDetector:
    def test_detect_payload_shape(self):
        from eis.modules.android.adb import detect

        result = detect()
        assert {"adb_found", "adb_path", "devices", "fastboot_devices"} <= set(result)
        assert isinstance(result["devices"], list)

    def test_fastboot_list_without_binary(self):
        from eis.modules.android.adb import list_fastboot_devices

        assert list_fastboot_devices() in ([], None) or isinstance(list_fastboot_devices(), list)


class TestConsoleSafety:
    def test_presets_are_curated(self):
        assert PRESETS
        for preset in PRESETS:
            assert preset[0] and preset[1]
            assert isinstance(preset[3], bool)  # destructive flag

    def test_manual_rejects_blocked(self):
        result = run_manual("adb shell su", confirmed=True)
        assert not result["ok"]
        assert result.get("blocked")

    def test_manual_requires_confirmation_for_reboot(self):
        result = run_manual("adb reboot")
        assert result.get("confirm_required")

    def test_manual_empty(self):
        assert not run_manual("")["ok"]

    def test_manual_parse_error(self):
        result = run_manual("adb shell 'unterminated")
        assert not result["ok"]


class TestLogcatBuffer:
    def test_parse_threadtime_line(self):
        line = "10-01 12:34:56.789  1234  5678 E AndroidRuntime: FATAL EXCEPTION"
        entry = LogcatBuffer._parse_line(line)
        assert entry["level"] == "E"
        assert entry["tag"] == "AndroidRuntime"
        assert "FATAL" in entry["message"]

    def test_parse_garbage_line(self):
        entry = LogcatBuffer._parse_line("this is not logcat format")
        assert entry["level"] == "?"
        assert entry["raw"] == "this is not logcat format"

    def test_query_filtering(self):
        buffer = LogcatBuffer(max_lines=100)
        buffer.lines = [
            {"time": "t1", "level": "E", "tag": "App", "pid": "1", "message": "boom", "raw": "r1"},
            {"time": "t2", "level": "I", "tag": "System", "pid": "2", "message": "info msg", "raw": "r2"},
            {"time": "t3", "level": "W", "tag": "Net", "pid": "3", "message": "slow wifi", "raw": "r3"},
        ]
        errors = buffer.query(min_level="E")
        assert len(errors) == 1 and errors[0]["level"] == "E"
        wifi = buffer.query(search="wifi")
        assert len(wifi) == 1 and wifi[0]["tag"] == "Net"
        counts = buffer.counts_by_level()
        assert counts["E"] == 1 and counts["I"] == 1 and counts["W"] == 1


class TestApkAnalyzer:
    def _make_apk(self, path: Path, manifest: bytes = b"\x03\x00\x08\x00" + b"\x00" * 60) -> Path:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("AndroidManifest.xml", manifest)
            zf.writestr("classes.dex", b"dex\n035")
        return path

    def test_valid_zip_parses_without_crash(self, tmp_path: Path):
        from eis.modules.android.apk import analyze

        apk = self._make_apk(tmp_path / "demo.apk")
        result = analyze(apk)
        assert result["ok"]
        assert result["dex_files"] == ["classes.dex"]
        assert result["permission_count"] == 0

    def test_missing_file(self, tmp_path: Path):
        from eis.modules.android.apk import analyze

        assert not analyze(tmp_path / "missing.apk")["ok"]

    def test_not_an_apk(self, tmp_path: Path):
        from eis.modules.android.apk import analyze

        target = tmp_path / "notapk.apk"
        target.write_bytes(b"plain text, not a zip")
        assert not analyze(target)["ok"]

    def test_wrong_extension(self, tmp_path: Path):
        from eis.modules.android.apk import analyze

        target = tmp_path / "file.exe"
        target.write_bytes(b"MZ...")
        assert not analyze(target)["ok"]


class TestPackageGates:
    def test_uninstall_requires_confirmation(self):
        from eis.modules.android.packages import change_package_state

        result = change_package_state("com.example.app", "uninstall", confirmed=False)
        assert result.get("confirm_required")
        assert "uninstall" in result["warning"].lower()

    def test_invalid_action_rejected(self):
        from eis.modules.android.packages import change_package_state

        assert not change_package_state("com.example.app", "format")["ok"]
