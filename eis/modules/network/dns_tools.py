"""DNS diagnostics: hostname resolution and common record lookups."""

from __future__ import annotations

import logging
import socket
import subprocess

log = logging.getLogger(__name__)

_RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR")


def resolve_hostname(host: str) -> dict:
    """Resolve a hostname to IPv4/IPv6 addresses."""
    host = (host or "").strip()
    if not host:
        return {"ok": False, "error": "Hostname required."}
    result: dict = {"ok": False, "host": host, "ipv4": [], "ipv6": [], "canonical": ""}
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        result["error"] = f"Resolution failed: {exc}"
        return result
    seen_v4, seen_v6 = set(), set()
    for family, _type, _proto, _canonname, sockaddr in infos:
        addr = sockaddr[0]
        if family == socket.AF_INET and addr not in seen_v4:
            seen_v4.add(addr)
            result["ipv4"].append(addr)
        elif family == socket.AF_INET6 and addr not in seen_v6:
            seen_v6.add(addr)
            result["ipv6"].append(addr)
    result["ok"] = bool(result["ipv4"] or result["ipv6"])
    return result


def reverse_lookup(ip: str) -> dict:
    try:
        host, _aliases, _addrs = socket.gethostbyaddr(ip.strip())
        return {"ok": True, "ip": ip, "hostname": host}
    except (socket.herror, socket.gaierror, OSError) as exc:
        return {"ok": False, "ip": ip, "error": str(exc)}


def lookup_records(host: str, record_type: str = "A", dns_server: str = "") -> dict:
    """Query DNS records using nslookup (stdlib-only, no extra dependency)."""
    host = (host or "").strip()
    record_type = record_type.upper().strip()
    if not host:
        return {"ok": False, "error": "Hostname required."}
    if record_type not in _RECORD_TYPES:
        return {"ok": False, "error": f"Unsupported record type: {record_type}"}

    args = ["nslookup", f"-type={record_type}", host]
    if dns_server:
        args.append(dns_server)
    try:
        proc = subprocess.run(args, capture_output=True, timeout=10, text=True)
        output = proc.stdout or proc.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc), "records": []}

    records = _parse_nslookup(output, record_type)
    return {
        "ok": bool(records),
        "host": host,
        "type": record_type,
        "server": dns_server or "system default",
        "records": records,
        "raw": output.strip(),
    }


def _parse_nslookup(output: str, record_type: str) -> list[str]:
    """Extract answer lines from nslookup output."""
    lines = output.splitlines()
    answers: list[str] = []
    in_answer = False
    for line in lines:
        low = line.lower()
        if low.strip().startswith(("server:", "address:", "set q=")):
            if "address" in low and in_answer and line.strip():
                answers.append(line.strip())
            continue
        if record_type.lower() in low or "internet address" in low or "mail exchanger" in low:
            in_answer = True
            text = line.strip()
            if text and not text.startswith("*"):
                answers.append(text)
    # de-duplicate, keep order
    seen = set()
    unique = []
    for a in answers:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique


def dns_benchmark(servers: list[str] | None = None, host: str = "google.com") -> dict:
    """Measure resolution latency against common DNS servers."""
    servers = servers or ["8.8.8.8", "1.1.1.1", "9.9.9.9", "208.67.222.222"]
    import time as _time

    results = []
    for server in servers:
        start = _time.perf_counter()
        res = lookup_records(host, "A", dns_server=server)
        elapsed = round((_time.perf_counter() - start) * 1000, 1)
        results.append({"server": server, "ok": res["ok"], "ms": elapsed if res["ok"] else None})
    return {"ok": True, "host": host, "results": results}
