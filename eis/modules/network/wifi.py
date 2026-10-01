"""Wi-Fi information: current connection details and nearby networks."""

from __future__ import annotations

import logging
import os
import re

from eis.core.command_runner import run_command

log = logging.getLogger(__name__)


def current_connection() -> dict:
    """Details of the active Wi-Fi connection (Windows netsh WLAN)."""
    if os.name != "nt":
        return {"ok": False, "error": "Windows-only feature."}
    res = run_command(["netsh", "wlan", "show", "interfaces"], timeout=15, check_safety=False)
    if not res.ok:
        return {"ok": False, "error": res.stderr or "netsh wlan failed (no Wi-Fi adapter?)"}
    text = res.stdout
    info: dict = {"ok": True}
    patterns = {
        "ssid": r"^\s*SSID\s*:\s*(.+)$",
        "bssid": r"^\s*BSSID\s*:\s*(.+)$",
        "adapter": r"^\s*Description\s*:\s*(.+)$",
        "state": r"^\s*State\s*:\s*(.+)$",
        "signal": r"^\s*Signal\s*:\s*(.+)$",
        "channel": r"^\s*Channel\s*:\s*(\d+)$",
        "radio_type": r"^\s*Radio type\s*:\s*(.+)$",
        "authentication": r"^\s*Authentication\s*:\s*(.+)$",
        "band": r"^\s*Band\s*:\s*(.+)$",
        "receive_rate": r"^\s*Receive rate \(Mbps\)\s*:\s*(\d+)$",
        "transmit_rate": r"^\s*Transmit rate \(Mbps\)\s*:\s*(\d+)$",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            info[key] = m.group(1).strip()
    # Convert signal to percentage + quality word
    if "signal" in info:
        m = re.search(r"(\d+)%", info["signal"])
        if m:
            pct = int(m.group(1))
            info["signal_percent"] = pct
            info["signal_quality"] = _quality_word(pct)
    return info


def _quality_word(pct: int) -> str:
    if pct >= 80:
        return "Excellent"
    if pct >= 60:
        return "Good"
    if pct >= 40:
        return "Fair"
    if pct >= 20:
        return "Weak"
    return "Very weak"


def nearby_networks() -> list[dict]:
    """Visible Wi-Fi networks (netsh wlan show networks mode=bssid)."""
    if os.name != "nt":
        return []
    res = run_command(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=20, check_safety=False)
    if not res.ok:
        return []
    networks: list[dict] = []
    current: dict = {}
    for line in res.stdout.splitlines():
        line = line.rstrip()
        m = re.match(r"^\s*SSID (\d+)\s*:\s*(.*)$", line)
        if m:
            if current.get("ssid") is not None:
                networks.append(current)
            current = {"ssid": m.group(2).strip(), "bssids": []}
            continue
        if not current:
            continue
        m = re.match(r"^\s*Authentication\s*:\s*(.+)$", line)
        if m:
            current["authentication"] = m.group(1).strip()
            continue
        m = re.match(r"^\s*Encryption\s*:\s*(.+)$", line)
        if m:
            current["encryption"] = m.group(1).strip()
            continue
        m = re.match(r"^\s*BSSID (\d+)\s*:\s*(.+)$", line)
        if m:
            current["bssids"].append({"bssid": m.group(2).strip()})
            continue
        m = re.match(r"^\s*Signal\s*:\s*(\d+)%", line)
        if m and current.get("bssids"):
            current["bssids"][-1]["signal_percent"] = int(m.group(1))
            continue
        m = re.match(r"^\s*Channel\s*:\s*(\d+)$", line)
        if m and current.get("bssids"):
            current["bssids"][-1]["channel"] = int(m.group(1))
    if current.get("ssid") is not None:
        networks.append(current)
    # Fill missing channel on bssid entries
    for net in networks:
        for b in net.get("bssids", []):
            b.setdefault("channel", None)
            b.setdefault("signal_percent", None)
    return networks


def saved_networks() -> list[dict]:
    """WLAN profiles saved on this machine (names only - no passwords)."""
    if os.name != "nt":
        return []
    res = run_command(["netsh", "wlan", "show", "profiles"], timeout=15, check_safety=False)
    if not res.ok:
        return []
    names = []
    for line in res.stdout.splitlines():
        m = re.search(r"All User Profile\s*:\s*(.+)$", line)
        if m:
            names.append(m.group(1).strip())
    return [{"name": n} for n in names]


def signal_report() -> dict:
    """Compact signal summary for the dashboard."""
    conn = current_connection()
    if not conn.get("ok"):
        return {"ok": False, "connected": False}
    return {
        "ok": True,
        "connected": "disconnected" not in conn.get("state", "").lower(),
        "ssid": conn.get("ssid", ""),
        "signal_percent": conn.get("signal_percent"),
        "quality": conn.get("signal_quality", ""),
        "channel": conn.get("channel"),
        "band": conn.get("band", ""),
        "adapter": conn.get("adapter", ""),
    }
