"""Authorized-target scope enforcement.

Every network-touching command in redkit goes through a :class:`Scope`.
The scope file (``$REDKIT_HOME/scope``, default ``~/.redkit/scope``) lists
the targets you are authorized to test: IP addresses, CIDR ranges and
domains, one per line. Blank lines and ``#`` comments are ignored.

Policy checks never touch the network: a hostname is in scope only if it
matches a domain entry exactly or as a subdomain. Add domains explicitly.
"""

from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union
from urllib.parse import urlsplit

__all__ = [
    "ScopeError",
    "EmptyScope",
    "OutOfScope",
    "Scope",
    "default_home",
]


class ScopeError(Exception):
    """Invalid scope configuration or a scope policy problem."""


class EmptyScope(ScopeError):
    """No scope entries configured; all network targets are refused."""


class OutOfScope(ScopeError):
    """A target was refused because it is not in the authorized scope."""

    def __init__(self, target: str):
        super().__init__(target)
        self.target = target

    def __str__(self) -> str:
        return f"{self.target!r} is not in the authorized scope"


def default_home() -> Path:
    """Directory for scope and findings data (override with REDKIT_HOME)."""
    env = os.environ.get("REDKIT_HOME")
    return Path(env) if env else Path.home() / ".redkit"


_DOMAIN_RE = re.compile(
    r"(?:\*\.)?"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)

_Parsed = Tuple[str, Union[ipaddress._BaseNetwork, str]]


class Scope:
    """The set of targets you are authorized to test."""

    def __init__(self, entries: Optional[Iterable[str]] = None):
        self._raw: List[str] = []
        self._networks: List[ipaddress._BaseNetwork] = []
        self._domains: List[str] = []
        for entry in entries or []:
            self.add(entry)

    # --- persistence -----------------------------------------------------

    @classmethod
    def load(cls, path) -> "Scope":
        p = Path(path)
        if not p.exists():
            return cls([])
        entries = []
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                entries.append(line)
        return cls(entries)

    def save(self, path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(e + "\n" for e in self._raw), encoding="utf-8")

    # --- entry management ------------------------------------------------

    @staticmethod
    def _parse(entry: str) -> _Parsed:
        e = entry.strip().lower()
        if not e:
            raise ScopeError("empty scope entry")
        try:
            return ("net", ipaddress.ip_network(e, strict=False))
        except ValueError:
            pass
        if not _DOMAIN_RE.fullmatch(e):
            raise ScopeError(
                f"invalid scope entry: {entry!r} (use an IP, a CIDR range or a domain)"
            )
        e = e[2:] if e.startswith("*.") else e
        return ("dom", e)

    def add(self, entry: str) -> bool:
        """Add an entry. Returns False if it was already present."""
        kind, value = self._parse(entry)
        raw = entry.strip().lower()
        if raw in self._raw:
            return False
        self._raw.append(raw)
        if kind == "net":
            self._networks.append(value)  # type: ignore[arg-type]
        else:
            self._domains.append(value)  # type: ignore[arg-type]
        return True

    def remove(self, entry: str) -> bool:
        kind, value = self._parse(entry)
        keep = [r for r in self._raw if self._parse(r) != (kind, value)]
        if len(keep) == len(self._raw):
            return False
        self._raw, self._networks, self._domains = [], [], []
        for r in keep:
            self.add(r)
        return True

    def entries(self) -> List[str]:
        return list(self._raw)

    def is_empty(self) -> bool:
        return not self._raw

    def __len__(self) -> int:
        return len(self._raw)

    # --- enforcement -----------------------------------------------------

    @staticmethod
    def _host_of(target: str) -> str:
        """Normalize a target to a bare host: strips scheme, port and path."""
        t = target.strip().lower().rstrip(".")
        if "://" in t:
            t = urlsplit(t).hostname or ""
        return t.strip()

    def allows(self, target: str) -> bool:
        host = self._host_of(target)
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return any(ip in net for net in self._networks)
        for domain in self._domains:
            if host == domain or host.endswith("." + domain):
                return True
        return False

    def require(self, target: str) -> None:
        """Raise OutOfScope unless *target* is authorized. Never touches the network."""
        if not self.allows(target):
            raise OutOfScope(target)


def load_scope(home: Optional[Path] = None) -> Scope:
    """Load the scope file from *home* (default: default_home())."""
    return Scope.load((home or default_home()) / "scope")
