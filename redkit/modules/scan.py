"""Host discovery and TCP port scanning.

Stdlib-only connect scan: works unprivileged on Android, and in a rooted
NetHunter Kali chroot you can run it as root like anything else. A thread
pool keeps scans fast while staying inside phone-friendly fd limits.

Every target passes through the Scope *before* a single packet is sent.
"""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

from ..scope import Scope

DEFAULT_PORTS = (
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
    993, 995, 1433, 1523, 3306, 3389, 5432, 5900, 8080, 8443,
)

# Ports we send a tiny HTTP probe to (others just wait for an unsolicited banner).
_PROBE_PORTS = {80, 443, 8080, 8443}
_BANNER_LEN = 128
_BANNER_WAIT = 1.5


@dataclass
class PortResult:
    host: str
    port: int
    state: str  # "open" | "closed" | "filtered"
    banner: str = ""


@dataclass
class ScanReport:
    targets: List[str] = field(default_factory=list)
    ports: List[int] = field(default_factory=list)
    open_ports: List[PortResult] = field(default_factory=list)
    hosts_up: List[str] = field(default_factory=list)

    @property
    def open_count(self) -> int:
        return len(self.open_ports)


def parse_targets(spec: str) -> List[str]:
    """Expand a target spec: CIDR, comma list, single IP or hostname."""
    out: List[str] = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        try:
            net = ipaddress.ip_network(part, strict=False)
        except ValueError:
            out.append(part)  # hostname or already-resolved name
            continue
        if net.version == 4 and net.prefixlen < 24:
            raise ValueError(
                f"{part} is too large ({net.num_addresses} hosts); "
                "scan at most a /24 at a time"
            )
        out.extend(str(h) for h in net.hosts()) if net.num_addresses > 2 else out.append(str(net.network_address))
    if not out:
        raise ValueError("no targets given")
    return out


def parse_ports(spec: str) -> List[int]:
    """Parse '22,80,443,8000-8100' into a sorted unique list."""
    ports: set = set()
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if not (1 <= lo <= hi <= 65535):
                raise ValueError(f"bad port range: {part}")
            if hi - lo > 10000:
                raise ValueError(f"port range too large: {part} (>10000 ports)")
            ports.update(range(lo, hi + 1))
        else:
            p = int(part)
            if not 1 <= p <= 65535:
                raise ValueError(f"bad port: {part}")
            ports.add(p)
    if not ports:
        raise ValueError("no ports given")
    return sorted(ports)


def _probe(host: str, port: int, timeout: float) -> Tuple[str, socket.socket | None]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return "open", sock
    except (ConnectionRefusedError, socket.timeout, OSError):
        return "closed", None
    finally:
        if sock.fileno() == -1:
            sock.close()


def _grab_banner(sock: socket.socket, probe: bool) -> str:
    sock.settimeout(_BANNER_WAIT)
    try:
        if probe:
            try:
                sock.sendall(b"HEAD / HTTP/1.0\r\nHost: redkit\r\n\r\n")
            except OSError:
                pass
        data = sock.recv(_BANNER_LEN)
        return data.decode("utf-8", "replace").strip().replace("\r", " ").replace("\n", " ")
    except OSError:
        return ""
    finally:
        try:
            sock.close()
        except OSError:
            pass


def scan_port(host: str, port: int, timeout: float = 1.0) -> PortResult:
    state, sock = _probe(host, port, timeout)
    banner = ""
    if state == "open" and sock is not None:
        # Web ports need a nudge; everything else (SSH, FTP, SMTP, ...)
        # announces itself as soon as we connect.
        banner = _grab_banner(sock, probe=port in _PROBE_PORTS)
    elif sock is not None:
        sock.close()
    return PortResult(host=host, port=port, state=state, banner=banner)


def run(
    target_spec: str,
    port_spec: str,
    scope: Scope,
    timeout: float = 1.0,
    workers: int = 64,
) -> ScanReport:
    """Scan. Raises OutOfScope before sending anything if a target is not authorized."""
    hosts = parse_targets(target_spec)
    ports = parse_ports(port_spec)
    for host in hosts:
        scope.require(host)  # fail closed, pre-packet

    report = ScanReport(targets=hosts, ports=ports)
    with ThreadPoolExecutor(max_workers=min(workers, 256)) as pool:
        futures = {
            pool.submit(scan_port, host, port, timeout): (host, port)
            for host in hosts
            for port in ports
        }
        for fut in as_completed(futures):
            result = fut.result()
            if result.state == "open":
                report.open_ports.append(result)
                if result.host not in report.hosts_up:
                    report.hosts_up.append(result.host)
    report.open_ports.sort(key=lambda r: (r.host, r.port))
    return report
