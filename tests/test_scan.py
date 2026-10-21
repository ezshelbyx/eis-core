import socket
import threading

import pytest

from redkit.modules import scan
from redkit.scope import OutOfScope, Scope


def test_parse_ports_mixed():
    assert scan.parse_ports("22,80,8000-8003") == [22, 80, 8000, 8001, 8002, 8003]


def test_parse_ports_dedup_sort():
    assert scan.parse_ports("443,80,443") == [80, 443]


def test_parse_ports_bad():
    with pytest.raises(ValueError):
        scan.parse_ports("0")
    with pytest.raises(ValueError):
        scan.parse_ports("70000")
    with pytest.raises(ValueError):
        scan.parse_ports("9000-1000")
    with pytest.raises(ValueError):
        scan.parse_ports("1-20001")


def test_parse_targets_cidr():
    hosts = scan.parse_targets("192.168.56.0/30")
    assert hosts == ["192.168.56.1", "192.168.56.2"]


def test_parse_targets_rejects_huge_cidr():
    with pytest.raises(ValueError):
        scan.parse_targets("10.0.0.0/8")


def test_parse_targets_hostname_passthrough():
    assert scan.parse_targets("localhost") == ["localhost"]
    assert scan.parse_targets("localhost, 127.0.0.1") == ["localhost", "127.0.0.1"]


def test_scan_refuses_out_of_scope_before_probe():
    scope = Scope([])  # nothing authorized
    with pytest.raises(OutOfScope):
        scan.run("127.0.0.1", "1-10", scope, timeout=0.05, workers=4)


def test_scan_localhost_open_port():
    # Bind a server socket on an ephemeral port, then scan it.
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]
    stop = threading.Event()

    def accept_loop():
        while not stop.is_set():
            try:
                srv.settimeout(0.2)
                conn, _ = srv.accept()
                conn.sendall(b"HELLO-REDKIT\r\n")
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break

    t = threading.Thread(target=accept_loop, daemon=True)
    t.start()
    try:
        scope = Scope(["127.0.0.1"])
        report = scan.run("127.0.0.1", str(port), scope, timeout=2.0, workers=8)
        assert report.open_count == 1
        result = report.open_ports[0]
        assert result.host == "127.0.0.1"
        assert result.port == port
        assert "HELLO-REDKIT" in result.banner
        assert report.hosts_up == ["127.0.0.1"]
    finally:
        stop.set()
        srv.close()
        t.join(timeout=2)


def test_scan_closed_port_reports_closed():
    # Grab a port by binding then closing it; it should be closed, not open.
    tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp.bind(("127.0.0.1", 0))
    port = tmp.getsockname()[1]
    tmp.close()

    scope = Scope(["127.0.0.1"])
    report = scan.run("127.0.0.1", str(port), scope, timeout=0.5, workers=4)
    assert report.open_count == 0
    assert report.hosts_up == []
