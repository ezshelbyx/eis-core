"""Local network discovery - safe and non-invasive.

Strategy: ARP table inspection + optional TCP connect checks on a small set of
management ports.  No packet injection, no ARP spoofing, no aggressive scans.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import time

from eis.core.command_runner import run_command

log = logging.getLogger(__name__)

CHECK_PORTS = (80, 443, 8080, 22, 445, 3389, 5353)


def arp_table() -> list[dict]:
    """Parse the system ARP table (read-only)."""
    if os.name == "nt":
        res = run_command(["arp", "-a"], timeout=15, check_safety=False)
    else:
        res = run_command(["ip", "neigh"], timeout=15, check_safety=False)
    if not res.ok:
        return []
    devices = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if os.name == "nt":
            m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\S+)", line)
            if m:
                devices.append(
                    {"ip": m.group(1), "mac": m.group(2).replace("-", ":").lower(),
                     "state": m.group(3)}
                )
        else:
            m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+\S+\s+(\S+)\s+(\S+)", line)
            if m and m.group(1) != "192.168.144.2" or (m and m.group(1)):
                devices.append({"ip": m.group(1), "mac": _normalize_mac(m.group(2)), "state": m.group(3)})
    seen = set()
    unique = []
    for d in devices:
        ip = d["ip"]
        mac = d["mac"]
        if ip in seen or mac == "ff:ff:ff:ff:ff:ff":
            continue
        if ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255"):
            continue  # multicast / broadcast
        seen.add(ip)
        unique.append(d)
    return unique


def _normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").lower() if re.match(r"^[0-9a-fA-F: -]{12,}$", mac) else mac


def _vendor_guess(mac: str) -> str:
    """Extremely small OUI hint list (local, no network calls)."""
    prefixes = {
        "00:1a:11": "Google", "00:50:56": "VMware", "08:00:27": "VirtualBox",
        "b8:27:eb": "Raspberry Pi", "dc:a6:32": "Raspberry Pi", "00:1b:44": "SanDisk",
        "3c:5a:b4": "Google", "f0:9f:c2": "Ubiquiti", "00:0c:29": "VMware",
        "d8:3a:dd": "Raspberry Pi", "28:cd:c1": "Raspberry Pi",
    }
    return prefixes.get(mac[:8].lower(), "")


def discover(scan_ports: bool = False, timeout_s: int = 5) -> dict:
    """Discover devices visible in the ARP cache; optionally probe common TCP ports."""
    started = time.time()
    devices = arp_table()
    results = []
    for dev in devices[:64]:  # safety cap
        entry = {
            "ip": dev["ip"],
            "mac": dev["mac"],
            "state": dev.get("state", ""),
            "vendor": _vendor_guess(dev["mac"]),
            "hostname": _reverse_host(dev["ip"], timeout=0.5),
        }
        if scan_ports:
            entry["open_ports"] = _quick_port_scan(dev["ip"], timeout_s=min(1.0, timeout_s / 10))
        results.append(entry)
    return {
        "ok": True,
        "count": len(results),
        "devices": results,
        "duration_s": round(time.time() - started, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Passive discovery via ARP cache. Enable port check for service hints.",
    }


def _reverse_host(ip: str, timeout: float = 0.5) -> str:
    socket.setdefaulttimeout(timeout)
    try:
        host, _aliases, _addrs = socket.gethostbyaddr(ip)
        return host
    except (socket.herror, socket.gaierror, OSError):
        return ""
    finally:
        socket.setdefaulttimeout(None)


def _quick_port_scan(ip: str, timeout_s: float = 1.0) -> list[int]:
    open_ports = []
    for port in CHECK_PORTS:
        try:
            with socket.create_connection((ip, port), timeout=timeout_s):
                open_ports.append(port)
        except (socket.timeout, OSError):
            continue
    return open_ports


def ping_sweep_cidr_single_octet(prefix: str, start: int = 1, end: int = 20, timeout_ms: int = 300) -> list[str]:
    """Lightweight sweep for small ranges (e.g. 192.168.1.x 1-20).  Optional helper."""
    alive = []
    for i in range(start, end + 1):
        ip = f"{prefix}.{i}"
        res = run_command(
            ["ping", "-n", "1", "-w", str(timeout_ms), ip] if os.name == "nt"
            else ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip],
            timeout=2, check_safety=False,
        )
        if res.ok:
            alive.append(ip)
    return alive
