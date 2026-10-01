"""Internet connectivity diagnostic: gateway -> DNS -> external hosts."""

from __future__ import annotations

import logging
import socket
import time

from eis.core.command_runner import run_command
from eis.modules.network.dns_tools import resolve_hostname
from eis.modules.network.ping import ping_host

log = logging.getLogger(__name__)

EXTERNAL_TARGETS = ("1.1.1.1", "8.8.8.8")


def run_connectivity_test(targets: tuple[str, ...] = EXTERNAL_TARGETS) -> dict:
    """Layered connectivity diagnosis with plain-language verdicts."""
    steps: list[dict] = []
    overall_ok = True

    # 1. Gateway -----------------------------------------------------------
    gateway = _default_gateway()
    if gateway:
        res = ping_host(gateway, count=2, timeout_ms=1000)
        steps.append(
            {
                "step": "Gateway",
                "target": gateway,
                "ok": res["ok"],
                "detail": f"avg {res['avg_ms']} ms" if res["ok"] else "no reply from gateway",
            }
        )
        if not res["ok"]:
            overall_ok = False
    else:
        steps.append({"step": "Gateway", "target": None, "ok": False,
                      "detail": "No default gateway found (adapter down or no DHCP?)"})
        overall_ok = False

    # 2. DNS resolution ------------------------------------------------------
    dns_res = resolve_hostname("google.com")
    steps.append(
        {
            "step": "DNS resolution",
            "target": "google.com",
            "ok": dns_res["ok"],
            "detail": ", ".join(dns_res.get("ipv4", [])[:2]) or dns_res.get("error", "failed"),
        }
    )
    if not dns_res["ok"]:
        overall_ok = False

    # 3. External hosts ------------------------------------------------------
    for target in targets:
        res = ping_host(target, count=2, timeout_ms=1500)
        steps.append(
            {
                "step": "Internet",
                "target": target,
                "ok": res["ok"],
                "detail": f"avg {res['avg_ms']} ms" if res["ok"] else "no reply",
            }
        )
        if not res["ok"]:
            overall_ok = False

    verdict = _verdict(steps)
    return {
        "ok": overall_ok,
        "steps": steps,
        "verdict": verdict,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _default_gateway() -> str:
    """Best-effort default gateway detection."""
    import os

    if os.name == "nt":
        res = run_command(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | "
             "Select-Object -First 1).NextHop"],
            timeout=15, check_safety=False,
        )
        ip = res.stdout.strip()
        if ip and _looks_like_ip(ip):
            return ip
        res = run_command(["route", "print", "0.0.0.0"], timeout=15, check_safety=False)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "0.0.0.0" and _looks_like_ip(parts[2]):
                return parts[2]
    else:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            pass
    return ""


def _looks_like_ip(text: str) -> bool:
    parts = text.strip().split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def _verdict(steps: list[dict]) -> str:
    failed = [s for s in steps if not s["ok"]]
    if not failed:
        return "Internet connectivity looks healthy."
    step_names = [s["step"] for s in failed]
    if "Gateway" in step_names:
        return "Local network problem: the gateway is unreachable. Check cables/Wi-Fi and router."
    if "DNS resolution" in step_names and "Internet" not in step_names:
        return "Connected but DNS is failing. Try changing DNS servers (e.g. 1.1.1.1 / 8.8.8.8) or flushing the cache."
    return "Gateway and DNS work but some external hosts are unreachable (possible ISP or firewall issue)."
