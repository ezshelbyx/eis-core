"""Tests for system information collection and monitors."""

from __future__ import annotations

import platform

from eis.modules.system.monitors import cpu_stats, ram_stats, uptime_summary
from eis.modules.system.psutil_bridge import PSUTIL_AVAILABLE
from eis.modules.system.storage import list_drives
from eis.modules.system.system_info import collect, uptime_seconds


class TestSystemInfo:
    def test_collect_returns_core_fields(self):
        info = collect(refresh_gpu=False)
        assert info["hostname"]
        assert info["system"] == platform.system()
        assert info["architecture"]
        assert info["uptime_seconds"] >= 0
        assert isinstance(info["is_admin"], bool)

    def test_uptime_positive(self):
        assert uptime_seconds() >= 0


class TestMonitors:
    def test_ram_stats_shape(self):
        ram = ram_stats()
        assert "total" in ram and "percent" in ram
        if ram["available"]:
            assert ram["total"] > 0
            assert 0 <= ram["percent"] <= 100

    def test_cpu_stats_shape(self):
        cpu = cpu_stats(interval=0.05)
        assert "percent_total" in cpu
        assert cpu["cores"] >= 1
        if PSUTIL_AVAILABLE and cpu["percent_total"] is not None:
            assert 0 <= cpu["percent_total"] <= 100

    def test_uptime_summary(self):
        summary = uptime_summary()
        assert "human" in summary and summary["seconds"] >= 0


class TestStorage:
    def test_list_drives_finds_system_drive(self):
        drives = list_drives()
        assert drives, "At least one drive must be visible"
        system_drive = [d for d in drives if d.get("mountpoint", "").rstrip("\\/") in ("C:", "C")]
        assert system_drive, "System drive missing from listing"
