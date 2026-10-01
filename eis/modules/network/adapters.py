"""Network adapters viewer: IPs, gateway, DNS, MAC, Wi-Fi state."""

from __future__ import annotations

import logging
import os
import socket

from eis.core.command_runner import run_powershell

log = logging.getLogger(__name__)


def list_adapters() -> list[dict]:
    """All network adapters with configuration details."""
    if os.name != "nt":
        return _posix_adapters()
    res = run_powershell(
        "Get-NetAdapter | Sort-Object Status -Descending | Select-Object Name,"
        "InterfaceDescription,Status,MacAddress,LinkSpeed,ifIndex | ConvertTo-Json -Compress",
        timeout=20, check_safety=False,
    )
    adapters = []
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                if_index = row.get("ifIndex")
                adapters.append(
                    {
                        "name": row.get("Name", ""),
                        "description": row.get("InterfaceDescription", ""),
                        "status": row.get("Status", ""),
                        "mac": row.get("MacAddress", ""),
                        "link_speed": row.get("LinkSpeed", ""),
                        "if_index": if_index,
                        "ip_config": _ip_config_for(if_index),
                        "dns_servers": _dns_for(if_index),
                    }
                )
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning("adapter parse error: %s", exc)
    return adapters


def _ip_config_for(if_index) -> dict:
    """IP addresses + gateway for one interface index."""
    out = {"ipv4": [], "ipv6": [], "gateway": []}
    if if_index is None:
        return out
    res = run_powershell(
        f"Get-NetIPAddress -InterfaceIndex {int(if_index)} -ErrorAction SilentlyContinue | "
        "Select-Object IPAddress,PrefixLength,AddressFamily | ConvertTo-Json -Compress",
        timeout=12, check_safety=False,
    )
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                addr = str(row.get("IPAddress", ""))
                if ":" in addr:
                    out["ipv6"].append(addr)
                else:
                    out["ipv4"].append(f"{addr}/{row.get('PrefixLength', '')}")
        except (json.JSONDecodeError, TypeError):
            pass
    res = run_powershell(
        f"Get-NetRoute -InterfaceIndex {int(if_index)} -DestinationPrefix '0.0.0.0/0' "
        "-ErrorAction SilentlyContinue | Select-Object -First 1 NextHop | ConvertTo-Json -Compress",
        timeout=12, check_safety=False,
    )
    if res.ok and res.stdout.strip():
        import json

        try:
            data = json.loads(res.stdout)
            row = data[0] if isinstance(data, list) else data
            out["gateway"] = [str(row.get("NextHop", ""))]
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
    return out


def _dns_for(if_index) -> list[str]:
    if if_index is None:
        return []
    res = run_powershell(
        f"Get-DnsClientServerAddress -InterfaceIndex {int(if_index)} -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty ServerAddresses",
        timeout=12, check_safety=False,
    )
    if res.ok and res.stdout.strip():
        return [l.strip() for l in res.stdout.splitlines() if l.strip()]
    return []


def _posix_adapters() -> list[dict]:
    """Minimal adapter info on non-Windows (development aid)."""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except OSError:
        ip = "127.0.0.1"
    return [
        {
            "name": "default",
            "description": hostname,
            "status": "Up",
            "mac": "",
            "link_speed": "",
            "if_index": None,
            "ip_config": {"ipv4": [ip], "ipv6": [], "gateway": []},
            "dns_servers": [],
        }
    ]


def public_ip() -> str:
    """Best-effort public IP via DNS resolution of OpenDNS (no HTTP dependency)."""
    try:
        import subprocess

        res = subprocess.run(
            ["nslookup", "myip.opendns.com", "resolver1.opendns.com"],
            capture_output=True, timeout=8, text=True,
        )
        for line in res.stdout.splitlines():
            if "Address" in line and "resolver1" not in line:
                candidate = line.split(":")[-1].strip()
                if candidate and not candidate.endswith("#53"):
                    return candidate
    except Exception:
        pass
    return ""
