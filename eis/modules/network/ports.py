"""TCP port diagnostics: test reachability of ports on a host."""

from __future__ import annotations

import logging
import socket
import time

log = logging.getLogger(__name__)

COMMON_PORTS = {
    20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 587: "SMTP submission", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 8080: "HTTP alt", 25565: "Minecraft",
}


def test_port(host: str, port: int, timeout: float = 2.0) -> dict:
    """Single TCP connect test."""
    host = (host or "").strip()
    if not host:
        return {"ok": False, "error": "Host required.", "port": port}
    if not (0 < port < 65536):
        return {"ok": False, "error": f"Invalid port: {port}", "host": host}
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            return {
                "ok": True, "host": host, "port": port,
                "service": COMMON_PORTS.get(port, ""),
                "open": True, "ms": elapsed,
            }
    except socket.timeout:
        return {"ok": True, "host": host, "port": port, "open": False,
                "service": COMMON_PORTS.get(port, ""), "reason": "timeout (filtered)"}
    except OSError as exc:
        reason = "connection refused" if "refused" in str(exc).lower() else str(exc)
        return {"ok": True, "host": host, "port": port, "open": False,
                "service": COMMON_PORTS.get(port, ""), "reason": reason}


def test_ports(host: str, ports: list[int], timeout: float = 2.0,
               stop_on_closed: bool = False) -> dict:
    """Test a list of ports sequentially; returns a summary."""
    results = []
    open_count = 0
    for port in ports:
        res = test_port(host, port, timeout)
        results.append(res)
        if res.get("open"):
            open_count += 1
        elif stop_on_closed and res.get("reason") == "connection refused":
            break
    return {
        "ok": True,
        "host": host,
        "tested": len(results),
        "open_count": open_count,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def scan_common_ports(host: str, timeout: float = 1.5) -> dict:
    """Scan the well-known ports defined in COMMON_PORTS."""
    return test_ports(host, sorted(COMMON_PORTS), timeout=timeout)
