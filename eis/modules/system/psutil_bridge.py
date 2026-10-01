"""Optional psutil integration for E.I.S. Core.

E.I.S. Core works without psutil (reduced detail) and uses it when present.
This bridge keeps a single import point so every module degrades the same way.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

try:  # pragma: no cover - depends on environment
    import psutil

    PSUTIL_AVAILABLE = True
except Exception:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    log.info("psutil not installed - running with reduced detail mode.")


def require_psutil() -> "psutil":  # type: ignore[name-defined]
    """Return the psutil module or raise a friendly RuntimeError."""
    if not PSUTIL_AVAILABLE:
        raise RuntimeError(
            "psutil is required for this feature. Install it with: pip install psutil"
        )
    return psutil  # type: ignore[return-value]


def status() -> dict:
    return {"available": PSUTIL_AVAILABLE, "version": getattr(psutil, "__version__", None)}
