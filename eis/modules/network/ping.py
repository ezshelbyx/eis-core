"""Ping diagnostics with latency statistics and session history."""

from __future__ import annotations

import logging
import re
import statistics
import time

from eis.core.command_runner import run_command
from eis.core.paths import record_command

log = logging.getLogger(__name__)

_PING_RE = re.compile(r"[=<>]\s*(\d+)ms", re.IGNORECASE)
_LOSS_RE = re.compile(r"\((\d+)%\s*(?:loss|perdu)")
_WINDOZE = re.compile(r"Minimum\s*=\s*(\d+)ms.*?Maximum\s*=\s*(\d+)ms.*?Average\s*=\s*(\d+)ms", re.IGNORECASE)


def ping_host(host: str, count: int = 4, timeout_ms: int = 1000) -> dict:
    """Ping *host* *count* times; returns parsed latency stats + per-reply log."""
    host = (host or "").strip()
    if not host:
        return {"ok": False, "error": "Host is required."}
    if count < 1 or count > 50:
        count = 4

    started = time.time()
    if _is_windows():
        args = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    else:
        args = ["ping", "-c", str(count), "-W", str(max(1, timeout_ms // 1000)), host]
    res = run_command(args, timeout=max(10, count * timeout_ms // 1000 + 10), check_safety=False)

    output = res.stdout or res.stderr
    latencies = [int(m) for m in _PING_RE.findall(output)]
    # The first match on Windows includes the byte-time prefix; keep the stats line numbers.
    loss_match = _LOSS_RE.search(output)
    loss_pct = int(loss_match.group(1)) if loss_match else (0 if res.ok and latencies else 100)

    stats_match = _WINDOZE.search(output)
    stats = {}
    if stats_match:
        stats = {"min": int(stats_match.group(1)), "max": int(stats_match.group(2)),
                 "avg": int(stats_match.group(3))}
    elif latencies:
        stats = {"min": min(latencies), "max": max(latencies),
                 "avg": round(statistics.mean(latencies), 1)}

    jitter = round(statistics.pstdev(latencies), 1) if len(latencies) > 1 else 0.0
    result = {
        "ok": res.ok and bool(latencies),
        "host": host,
        "sent": count,
        "received": len(latencies),
        "loss_percent": loss_pct if not res.ok else min(loss_pct, 100),
        "latencies_ms": latencies,
        "min_ms": stats.get("min"),
        "max_ms": stats.get("max"),
        "avg_ms": stats.get("avg"),
        "jitter_ms": jitter,
        "duration_s": round(time.time() - started, 2),
        "output": output.strip(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    record_command("network.ping", command=f"ping {host} x{count}",
                   result="ok" if result["ok"] else "error", error=None if result["ok"] else output[:200],
                   details={"avg_ms": result["avg_ms"], "loss": result["loss_percent"]})
    return result


def _is_windows() -> bool:
    import os

    return os.name == "nt"


class PingHistory:
    """In-memory rolling history of ping results for the UI."""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.entries: list[dict] = []

    def add(self, result: dict) -> None:
        self.entries.append(
            {
                "host": result.get("host"),
                "avg_ms": result.get("avg_ms"),
                "loss": result.get("loss_percent"),
                "ok": result.get("ok"),
                "timestamp": result.get("timestamp"),
            }
        )
        self.entries = self.entries[-self.max_entries:]

    def as_text(self) -> str:
        lines = [f"{'time':<20} {'host':<28} {'avg ms':>8} {'loss %':>8}"]
        for e in self.entries:
            lines.append(
                f"{e['timestamp'] or '?':<20} {e['host']:<28} {str(e['avg_ms'] if e['avg_ms'] is not None else '-'):>8} {str(e['loss'] if e['loss'] is not None else '-'):>8}"
            )
        return "\n".join(lines)
