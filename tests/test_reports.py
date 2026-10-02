"""Tests for the diagnostic report generator."""

from __future__ import annotations

import json
from pathlib import Path

from eis.modules.reports.generator import collect_snapshot, generate_report, render_html, render_txt


class TestRenderers:
    def test_txt_contains_sections(self):
        snapshot = {
            "meta": {"tool": "E.I.S. Core", "version": "0.1.0", "generated": "2026-01-01 10:00:00"},
            "system": {"info": {"hostname": "PC1", "os_edition": "Windows 10 Pro",
                                "os_build": "19045.1", "architecture": "AMD64",
                                "cpu_name": "Test CPU", "cpu_cores": 4, "cpu_threads": 8,
                                "motherboard": "TestBoard", "bios_vendor": "TestBIOS",
                                "bios_version": "1.0", "ram_total_gb": 16,
                                "gpus": ["TestGPU"], "is_admin": False, "uptime_seconds": 3600},
                       "uptime": {"seconds": 3600},
                       "ram": {"total": 16 * 1024 ** 3, "used": 8 * 1024 ** 3,
                               "available_bytes": 8 * 1024 ** 3, "percent": 50.0,
                               "swap_total": 4 * 1024 ** 3, "swap_used": 1024 ** 3, "swap_percent": 25.0},
                       "drives": [{"device": "C:", "fstype": "NTFS", "total": 100, "free": 50, "percent": 50}]},
            "windows": {"os": {"edition": "Windows 10 Pro", "build_full": "19045.1",
                               "release_name": "Windows 10 22H2", "install_date": "n/a"}},
            "network": {"adapters": [{"name": "Wi-Fi", "status": "Up", "mac": "AA:BB",
                                      "ip_config": {"ipv4": ["192.168.0.2/24"], "gateway": ["192.168.0.1"]},
                                      "dns_servers": ["1.1.1.1"]}]},
        }
        text = render_txt(snapshot)
        assert "[SYSTEM]" in text and "[MEMORY]" in text and "[STORAGE]" in text
        assert "[WINDOWS]" in text and "[NETWORK]" in text
        assert "PC1" in text

    def test_html_is_self_contained(self):
        html = render_html({"meta": {"tool": "E.I.S. Core", "version": "1", "generated": "x"}})
        assert html.startswith("<!DOCTYPE html>")
        assert "<style>" in html
        assert "src=" not in html or "cdn" not in html  # no external scripts required

    def test_html_escapes_values(self):
        html = render_html({
            "meta": {"tool": "<script>alert(1)</script>", "version": "1", "generated": "x"},
            "system": {"info": {"hostname": "<img src=x onerror=alert(1)>",
                                "os_edition": "W", "os_build": "1", "architecture": "x",
                                "cpu_name": "c", "cpu_cores": 1, "cpu_threads": 1,
                                "motherboard": "m", "bios_vendor": "b", "bios_version": "v",
                                "ram_total_gb": 8, "gpus": [], "uptime_seconds": 1},
                       "uptime": {"seconds": 1}},
        })
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestGenerate:
    def test_json_report_roundtrip(self, tmp_path: Path):
        result = generate_report("json", sections=["system"], dest_dir=tmp_path)
        assert result["ok"]
        data = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert "meta" in data and "system" in data

    def test_txt_report(self, tmp_path: Path):
        result = generate_report("txt", sections=["system"], dest_dir=tmp_path)
        assert result["ok"]
        assert Path(result["path"]).read_text(encoding="utf-8").startswith("=")

    def test_html_report(self, tmp_path: Path):
        result = generate_report("html", dest_dir=tmp_path)
        assert result["ok"]
        assert Path(result["path"]).suffix == ".html"

    def test_invalid_format_rejected(self, tmp_path: Path):
        assert not generate_report("pdf", dest_dir=tmp_path)["ok"]

    def test_snapshot_collects_meta(self):
        snapshot = collect_snapshot(sections=[])
        assert "meta" in snapshot
        assert snapshot["meta"]["tool"]
