"""Web security header audit.

Checks a URL you are authorized to test for missing hardening headers,
verbose server disclosure, insecure cookies, and a handful of well-known
misconfiguration paths (.git/HEAD, /.env, /server-status).

stdlib urllib only - no requests, no pip, works straight in the Kali chroot.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from ..scope import Scope

USER_AGENT = "redkit/0.1 (authorized security testing)"

# Header -> (severity if missing, why it matters)
SECURITY_HEADERS = {
    "strict-transport-security": ("medium", "browsers not forced to use HTTPS"),
    "content-security-policy": ("medium", "no XSS blast-radius control"),
    "x-frame-options": ("low", "clickjacking possible"),
    "x-content-type-options": ("low", "MIME sniffing possible"),
    "referrer-policy": ("info", "full referrer may leak"),
    "permissions-policy": ("info", "powerful browser features not restricted"),
}

DISCLOSE_HEADERS = ("server", "x-powered-by", "x-aspnet-version", "x-generator")

# Path -> severity when it returns 200
PROBE_PATHS = {
    "/.git/HEAD": "high",
    "/.env": "high",
    "/server-status": "medium",
    "/.svn/entries": "medium",
    "/backup.zip": "medium",
    "/phpinfo.php": "medium",
}

_PROBE_TIMEOUT = 6.0


@dataclass
class WebReport:
    url: str = ""
    status: int = 0
    final_url: str = ""
    missing_headers: List[str] = field(default_factory=list)
    disclosures: Dict[str, str] = field(default_factory=dict)
    cookie_issues: List[str] = field(default_factory=list)
    exposed_paths: Dict[str, int] = field(default_factory=dict)
    findings: List[dict] = field(default_factory=list)


def _fetch(url: str, timeout: float, method: str = "GET") -> tuple:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # audit targets often have broken certs
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), url


def audit(url: str, scope: Scope, timeout: float = _PROBE_TIMEOUT, probe_paths: bool = True) -> WebReport:
    """Audit *url*. Raises OutOfScope before any request if not authorized."""
    scope.require(url)  # fail closed, pre-request

    report = WebReport(url=url)
    status, headers, final_url = _fetch(url, timeout)
    report.status = status
    report.final_url = final_url
    lower = {k.lower(): v for k, v in headers.items()}

    for hdr, (severity, why) in SECURITY_HEADERS.items():
        if hdr not in lower:
            report.missing_headers.append(hdr)
            report.findings.append(
                {
                    "module": "web",
                    "target": url,
                    "title": f"Missing header: {hdr}",
                    "severity": severity,
                    "detail": why,
                }
            )

    for hdr in DISCLOSE_HEADERS:
        if hdr in lower and lower[hdr]:
            report.disclosures[hdr] = lower[hdr]
            report.findings.append(
                {
                    "module": "web",
                    "target": url,
                    "title": f"Server disclosure: {hdr}",
                    "severity": "info",
                    "detail": lower[hdr],
                }
            )

    set_cookie = lower.get("set-cookie", "")
    if set_cookie:
        cookie = set_cookie.lower()
        if "secure" not in cookie and urlparse(url).scheme == "https":
            report.cookie_issues.append("missing Secure flag")
            report.findings.append(
                {
                    "module": "web",
                    "target": url,
                    "title": "Cookie without Secure flag",
                    "severity": "medium",
                    "detail": set_cookie.split(";")[0],
                }
            )
        if "httponly" not in cookie:
            report.cookie_issues.append("missing HttpOnly flag")
            report.findings.append(
                {
                    "module": "web",
                    "target": url,
                    "title": "Cookie without HttpOnly flag",
                    "severity": "low",
                    "detail": set_cookie.split(";")[0],
                }
            )

    if probe_paths:
        parts = urlparse(final_url)
        base_path = parts.path or "/"
        if not base_path.endswith("/"):
            base_path = base_path.rsplit("/", 1)[0] + "/"
        base = f"{parts.scheme}://{parts.netloc}{base_path}"
        for path, severity in PROBE_PATHS.items():
            probe_url = urljoin(base, path)
            scope.require(probe_url)
            try:
                p_status, _, _ = _fetch(probe_url, timeout, method="GET")
            except (urllib.error.URLError, OSError, ValueError):
                continue
            if p_status == 200:
                report.exposed_paths[path] = p_status
                report.findings.append(
                    {
                        "module": "web",
                        "target": url,
                        "title": f"Exposed path: {path}",
                        "severity": severity,
                        "detail": f"HTTP {p_status}",
                    }
                )

    return report
