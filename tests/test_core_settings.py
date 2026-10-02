"""Tests for core settings, utils and command history."""

from __future__ import annotations

import json
from pathlib import Path

from eis.core.settings import DEFAULTS, Settings
from eis.core.utils import (
    app_title,
    clamp,
    file_sha256,
    format_bytes,
    format_duration,
    format_percent,
    safe_filename,
)


class TestSettings:
    def test_defaults_loaded_when_missing(self, tmp_path: Path):
        s = Settings(tmp_path / "settings.json")
        assert s.get("appearance.mode") == DEFAULTS["appearance.mode"]
        assert s.get("logging.level") == "INFO"

    def test_set_and_persist(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        s = Settings(path)
        s.set("appearance.font_size", 12)
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["appearance.font_size"] == 12

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text("{not valid json!!", encoding="utf-8")
        s = Settings(path)
        assert s.get("network.default_ping_count") == DEFAULTS["network.default_ping_count"]

    def test_font_size_normalized(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"appearance.font_size": 99}), encoding="utf-8")
        s = Settings(path)
        assert s.get("appearance.font_size") == 16  # clamped

    def test_reset(self, tmp_path: Path):
        s = Settings(tmp_path / "settings.json")
        s.set("appearance.mode", "dark")
        s.reset()
        assert s.get("appearance.mode") == DEFAULTS["appearance.mode"]


class TestUtils:
    def test_format_bytes(self):
        assert format_bytes(0) == "0 B"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(1024 ** 3).endswith("GB")

    def test_format_duration(self):
        assert format_duration(90061) == "1d 1h 1m 1s"
        assert format_duration(0) == "0s"

    def test_format_percent(self):
        assert format_percent(50) == "50.0%"

    def test_safe_filename(self):
        assert safe_filename("my report: final?.txt") != "my report: final?.txt"
        assert safe_filename("") == "untitled"

    def test_clamp(self):
        assert clamp(5, 0, 10) == 5
        assert clamp(-1, 0, 10) == 0

    def test_app_title(self):
        assert "E.I.S. Core" in app_title()
        assert app_title(version=False) == "E.I.S. Core"

    def test_file_sha256(self, tmp_path: Path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        import hashlib

        assert file_sha256(f) == hashlib.sha256(b"abc").hexdigest()
