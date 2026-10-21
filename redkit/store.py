"""Findings storage: every module records results as JSON lines.

Data lives in ``$REDKIT_HOME/findings.jsonl`` (default ``~/.redkit``) so a
report can be assembled across several commands during one engagement.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from .scope import default_home

VALID_SEVERITIES = ("info", "low", "medium", "high", "critical")


@dataclass
class Finding:
    module: str
    target: str
    title: str
    severity: str = "info"
    detail: str = ""
    data: dict = field(default_factory=dict)
    ts: str = ""

    def __post_init__(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {VALID_SEVERITIES}, got {self.severity!r}"
            )
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat(timespec="seconds")


def findings_path(home: Optional[Path] = None) -> Path:
    return (home or default_home()) / "findings.jsonl"


def record(finding: Finding, home: Optional[Path] = None) -> Path:
    path = findings_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(finding), ensure_ascii=False) + "\n")
    return path


def load(home: Optional[Path] = None) -> List[Finding]:
    path = findings_path(home)
    if not path.exists():
        return []
    out: List[Finding] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            out.append(Finding(**raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue  # tolerate hand-edited or partially written lines
    return out


def clear(home: Optional[Path] = None) -> bool:
    path = findings_path(home)
    if path.exists():
        path.unlink()
        return True
    return False
