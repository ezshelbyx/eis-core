"""Tests for network tools (offline-safe: ports + parsers, no external calls)."""

from __future__ import annotations

import socket

import pytest

# Aliased so pytest does not collect the imported functions as tests
# (their names start with test_).
from eis.modules.network.ports import COMMON_PORTS
from eis.modules.network.ports import test_port as port_probe
from eis.modules.network.ports import test_ports as ports_probe


class TestPortTool:
    def test_localhost_closed_port(self):
        # Bind then close to grab a guaranteed-free port.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            free_port = sock.getsockname()[1]
        result = port_probe("127.0.0.1", free_port, timeout=1)
        assert result["ok"]
        assert not result["open"]

    def test_live_localhost_listener(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            result = port_probe("127.0.0.1", port, timeout=2)
            assert result["open"]
            assert result["ms"] is not None
        finally:
            server.close()

    def test_invalid_port_rejected(self):
        result = port_probe("127.0.0.1", 99999)
        assert not result["ok"]
        assert "Invalid port" in result["error"]

    def test_batch_summary(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            free_port = sock.getsockname()[1]
        summary = ports_probe("127.0.0.1", [free_port, free_port + 1])
        assert summary["tested"] == 2
        assert summary["open_count"] == 0

    def test_common_ports_catalog(self):
        assert 22 in COMMON_PORTS and 443 in COMMON_PORTS


class TestPingParsing:
    def test_ping_requires_host(self):
        from eis.modules.network.ping import ping_host

        result = ping_host("")
        assert not result["ok"]
        assert "required" in result["error"].lower()

    def test_ping_count_clamped(self):
        from eis.modules.network.ping import PingHistory

        history = PingHistory(max_entries=3)
        for i in range(5):
            history.add({"host": f"h{i}", "avg_ms": i, "loss": 0, "ok": True, "timestamp": str(i)})
        assert len(history.entries) == 3  # rolling window
        assert "host" in history.as_text()


class TestDNSParsing:
    def test_lookup_rejects_bad_type(self):
        from eis.modules.network.dns_tools import lookup_records

        result = lookup_records("example.com", "BOGUS")
        assert not result["ok"]

    def test_reverse_lookup_local(self):
        from eis.modules.network.dns_tools import reverse_lookup

        result = reverse_lookup("127.0.0.1")
        assert result["ok"]
        assert result["hostname"]

    def test_resolve_requires_host(self):
        from eis.modules.network.dns_tools import resolve_hostname

        assert not resolve_hostname("")["ok"]


@pytest.mark.parametrize("payload,expected_sub", [
    ("WIFI:T:WPA;S:Net;P:pass;;", "WIFI:T:WPA"),
    ("https://example.com", "https://example.com"),
])
def test_qr_payload_shapes(payload, expected_sub):
    assert expected_sub in payload
