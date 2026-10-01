"""Diagnostic report generator: TXT, JSON and HTML exports.

Collects snapshots from System / Windows / Network modules into one report.
HTML reports are self-contained single files (inline CSS, print-friendly).
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from eis import APP_NAME, APP_VERSION
from eis.core.logging_config import REPORT_DIR
from eis.core.paths import record_command
from eis.core.utils import format_bytes, format_duration, jdump

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Snapshot collection
# ---------------------------------------------------------------------------

def collect_snapshot(sections: list[str] | None = None) -> dict:
    """Gather a diagnostic snapshot.  Missing pieces degrade to error strings."""
    wanted = sections or ["system", "windows", "network"]
    snapshot: dict[str, Any] = {
        "meta": {
            "tool": APP_NAME,
            "version": APP_VERSION,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

    if "system" in wanted:
        try:
            from eis.modules.system.monitors import cpu_stats, ram_stats, uptime_summary
            from eis.modules.system.storage import list_drives
            from eis.modules.system.system_info import collect as sys_collect

            snapshot["system"] = {
                "info": sys_collect(refresh_gpu=True),
                "cpu": cpu_stats(interval=0.2),
                "ram": ram_stats(),
                "uptime": uptime_summary(),
                "drives": list_drives(),
            }
        except Exception as exc:  # pragma: no cover
            snapshot["system"] = {"error": str(exc)}

    if "windows" in wanted:
        try:
            from eis.modules.windows.os_info import detect as os_detect

            snapshot["windows"] = {"os": os_detect()}
        except Exception as exc:  # pragma: no cover
            snapshot["windows"] = {"error": str(exc)}

    if "network" in wanted:
        try:
            from eis.modules.network.adapters import list_adapters

            snapshot["network"] = {"adapters": list_adapters()}
        except Exception as exc:  # pragma: no cover
            snapshot["network"] = {"error": str(exc)}

    return snapshot


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_txt(snapshot: dict) -> str:
    meta = snapshot.get("meta", {})
    lines = [
        "=" * 70,
        f"{meta.get('tool', 'E.I.S. Core')} - Diagnostic Report",
        f"Generated: {meta.get('generated', '')}   Version: {meta.get('version', '')}",
        "=" * 70,
        "",
    ]

    sysinfo = snapshot.get("system", {})
    if "error" not in sysinfo:
        info = sysinfo.get("info", {})
        lines += [
            "[SYSTEM]",
            f"  Hostname     : {info.get('hostname', '?')}",
            f"  OS           : {info.get('os_edition', '?')} {info.get('os_build', '')}",
            f"  Architecture : {info.get('architecture', '?')}",
            f"  CPU          : {info.get('cpu_name', '?')}",
            f"  Cores/Threads: {info.get('cpu_cores', '?')}/{info.get('cpu_threads', '?')}",
            f"  Motherboard  : {info.get('motherboard', '?')}",
            f"  BIOS         : {info.get('bios_vendor', '?')} {info.get('bios_version', '')}",
            f"  RAM total    : {info.get('ram_total_gb', '?')} GB",
            f"  Uptime       : {format_duration(sysinfo.get('uptime', {}).get('seconds', 0))}",
            f"  Administrator: {info.get('is_admin', False)}",
            "",
        ]
        gpus = info.get("gpus", [])
        if gpus:
            lines += ["  GPUs:"]
            for gpu in gpus:
                lines.append(f"    - {gpu}")
            lines.append("")

        ram = sysinfo.get("ram", {})
        if ram.get("total"):
            lines += [
                "[MEMORY]",
                f"  Total        : {format_bytes(ram['total'])}",
                f"  Used         : {format_bytes(ram['used'])} ({ram.get('percent', 0)}%)",
                f"  Available    : {format_bytes(ram['available_bytes'])}",
                f"  Swap         : {format_bytes(ram.get('swap_used', 0))} / {format_bytes(ram.get('swap_total', 0))}",
                "",
            ]

        drives = sysinfo.get("drives", [])
        if drives:
            lines += ["[STORAGE]"]
            for d in drives:
                total = format_bytes(d.get("total", 0))
                free = format_bytes(d.get("free", 0))
                lines.append(
                    f"  {d.get('device', '?'):<10} {d.get('fstype', '?'):<8} "
                    f"total {total:>10}  free {free:>10}  ({d.get('percent', 0)}% used)"
                )
            lines.append("")

    win = snapshot.get("windows", {})
    if "error" not in win and win.get("os"):
        os_info = win["os"]
        lines += [
            "[WINDOWS]",
            f"  Edition      : {os_info.get('edition', '?')}",
            f"  Build        : {os_info.get('build_full', os_info.get('build', '?'))}",
            f"  Release      : {os_info.get('release_name', '?')}",
            f"  Install date : {os_info.get('install_date', 'n/a')}",
            "",
        ]

    net = snapshot.get("network", {})
    if "error" not in net:
        adapters = net.get("adapters", [])
        if adapters:
            lines += ["[NETWORK]"]
            for a in adapters:
                lines.append(f"  {a.get('name', '?')} ({a.get('status', '?')}) MAC: {a.get('mac', 'n/a')}")
                ip = a.get("ip_config", {})
                if ip.get("ipv4"):
                    lines.append(f"    IPv4: {', '.join(ip['ipv4'])}")
                if ip.get("gateway"):
                    lines.append(f"    Gateway: {', '.join(ip['gateway'])}")
                if a.get("dns_servers"):
                    lines.append(f"    DNS: {', '.join(a['dns_servers'])}")
            lines.append("")

    lines += ["-- End of report --"]
    return "\n".join(lines)


def render_html(snapshot: dict) -> str:
    """Self-contained, print-friendly HTML report."""

    def table(rows: list[tuple[str, str]]) -> str:
        if not rows:
            return ""
        body = "".join(
            f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
            for k, v in rows
        )
        return f"<table>{body}</table>"

    meta = snapshot.get("meta", {})
    sysinfo = snapshot.get("system", {})
    sys_rows: list[tuple[str, str]] = []
    if "error" not in sysinfo:
        info = sysinfo.get("info", {})
        sys_rows = [
            ("Hostname", info.get("hostname", "?")),
            ("Operating system", f"{info.get('os_edition', '?')} {info.get('os_build', '')}"),
            ("Architecture", info.get("architecture", "?")),
            ("CPU", info.get("cpu_name", "?")),
            ("Cores / threads", f"{info.get('cpu_cores', '?')} / {info.get('cpu_threads', '?')}"),
            ("Motherboard", info.get("motherboard", "?")),
            ("BIOS", f"{info.get('bios_vendor', '?')} {info.get('bios_version', '')}"),
            ("GPU(s)", "; ".join(info.get("gpus", [])) or "n/a"),
            ("RAM", f"{info.get('ram_total_gb', '?')} GB"),
            ("Uptime", format_duration(sysinfo.get("uptime", {}).get("seconds", 0))),
        ]

    ram = sysinfo.get("ram", {}) if "error" not in sysinfo else {}
    ram_rows = []
    if ram.get("total"):
        ram_rows = [
            ("Total", format_bytes(ram["total"])),
            ("Used", f"{format_bytes(ram['used'])} ({ram.get('percent', 0)}%)"),
            ("Available", format_bytes(ram["available_bytes"])),
            ("Swap", f"{format_bytes(ram.get('swap_used', 0))} / {format_bytes(ram.get('swap_total', 0))}"),
        ]

    drive_rows = []
    for d in sysinfo.get("drives", []) if "error" not in sysinfo else []:
        drive_rows.append(
            (
                d.get("device", "?"),
                f"{d.get('fstype', '?')} - total {format_bytes(d.get('total', 0))}, "
                f"free {format_bytes(d.get('free', 0))} ({d.get('percent', 0)}% used)",
            )
        )

    win = snapshot.get("windows", {})
    win_rows = []
    if "error" not in win and win.get("os"):
        os_info = win["os"]
        win_rows = [
            ("Edition", os_info.get("edition", "?")),
            ("Build", os_info.get("build_full", os_info.get("build", "?"))),
            ("Release", os_info.get("release_name", "?")),
            ("Install date", os_info.get("install_date", "n/a")),
        ]

    net_rows = []
    for a in snapshot.get("network", {}).get("adapters", []):
        ip = a.get("ip_config", {})
        net_rows.append(
            (
                f"{a.get('name', '?')} ({a.get('status', '?')})",
                f"MAC {a.get('mac', 'n/a')} | IPv4 {', '.join(ip.get('ipv4', []) or ['-'])} | "
                f"GW {', '.join(ip.get('gateway', []) or ['-'])} | DNS {', '.join(a.get('dns_servers', []) or ['-'])}",
            )
        )

    css = """
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 32px auto; max-width: 900px;
           color: #1c2733; line-height: 1.5; }
    h1 { border-bottom: 3px solid #0f6cbd; padding-bottom: 8px; }
    h2 { color: #0f6cbd; margin-top: 28px; }
    table { border-collapse: collapse; width: 100%; margin: 10px 0; }
    td { border: 1px solid #d5dbe1; padding: 7px 10px; }
    td:first-child { background: #f0f4f8; font-weight: 600; width: 32%; }
    .meta { color: #5a6572; font-size: 0.9em; }
    footer { margin-top: 40px; color: #5a6572; font-size: 0.85em;
             border-top: 1px solid #d5dbe1; padding-top: 10px; }
    @media print { body { margin: 10mm; } }
    """

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(str(meta.get('tool', 'E.I.S. Core')))} - Diagnostic Report</title>",
        f"<style>{css}</style></head><body>",
        f"<h1>{html.escape(str(meta.get('tool', 'E.I.S. Core')))} - Diagnostic Report</h1>",
        f"<p class='meta'>Generated {html.escape(str(meta.get('generated', '')))} - "
        f"version {html.escape(str(meta.get('version', '')))}</p>",
        "<h2>System</h2>", table(sys_rows),
        "<h2>Memory</h2>", table(ram_rows),
        "<h2>Storage</h2>", table(drive_rows),
        "<h2>Windows</h2>", table(win_rows),
        "<h2>Network adapters</h2>", table(net_rows),
        f"<footer>Generated by {html.escape(str(meta.get('tool', 'E.I.S. Core')))} - "
        "open-source technician toolkit. MIT licensed.</footer>",
        "</body></html>",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(fmt: str = "html", sections: list[str] | None = None,
                    dest_dir: Path | None = None, snapshot: dict | None = None) -> dict:
    """Generate and save a diagnostic report.  Returns {ok, path, format}."""
    fmt = fmt.lower()
    if fmt not in ("txt", "json", "html"):
        return {"ok": False, "error": f"Unsupported format: {fmt}"}
    snap = snapshot if snapshot is not None else collect_snapshot(sections)
    dest_dir = Path(dest_dir) if dest_dir else REPORT_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = dest_dir / f"eis_report_{stamp}.{fmt}"

    try:
        if fmt == "json":
            path.write_text(jdump(snap), encoding="utf-8")
        elif fmt == "txt":
            path.write_text(render_txt(snap), encoding="utf-8")
        else:
            path.write_text(render_html(snap), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    record_command("report.generate", command=str(path), result="ok",
                   details={"format": fmt, "sections": sections or "all"})
    return {"ok": True, "path": str(path), "format": fmt, "size": path.stat().st_size}
