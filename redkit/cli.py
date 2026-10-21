"""redkit command line interface.

Subcommands:
  scope add|remove|list|show   manage the authorized-target list
  scan <targets> -p <ports>    TCP connect scan (scope-gated)
  web <url>                    security header audit (scope-gated)
  report                       summarize stored findings
  selftest                     run built-in checks, no network

Scope is empty by default: every network command refuses to run until you
add targets you are authorized to test.
"""

from __future__ import annotations

import argparse
import socket
import sys
from typing import List, Optional

from . import __version__
from .scope import EmptyScope, OutOfScope, Scope, ScopeError, default_home, load_scope
from .store import Finding, clear as clear_findings, load as load_findings, record

DEFAULT_SCAN_PORTS = "21,22,23,25,53,80,110,135,139,143,443,445,993,3306,3389,8080,8443"


def _require_scope(scope: Scope) -> None:
    if scope.is_empty():
        raise EmptyScope(
            "scope is empty - refusing to scan anything.\n"
            "Add targets you own or are authorized to test:\n"
            "  redkit scope add 192.168.1.0/24\n"
            "  redkit scope add example.com"
        )


def _save_scope(scope: Scope) -> None:
    scope.save(default_home() / "scope")


# --- scope subcommands -----------------------------------------------------

def cmd_scope(args: argparse.Namespace) -> int:
    scope = load_scope()
    if args.scope_cmd == "add":
        added = [e for e in args.entries if scope.add(e)]
        _save_scope(scope)
        for e in added:
            print(f"scope + {e}")
        if not added:
            print("nothing new added")
    elif args.scope_cmd == "remove":
        for e in args.entries:
            if scope.remove(e):
                print(f"scope - {e}")
            else:
                print(f"not in scope: {e}", file=sys.stderr)
        _save_scope(scope)
    elif args.scope_cmd == "list":
        if scope.is_empty():
            print("scope is empty (add targets with: redkit scope add <ip|cidr|domain>)")
        for e in scope.entries():
            print(e)
    elif args.scope_cmd == "show":
        print(default_home() / "scope")
    return 0


# --- scan ------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    from .modules import scan as scan_mod

    scope = load_scope()
    _require_scope(scope)
    try:
        report = scan_mod.run(
            args.targets, args.ports, scope,
            timeout=args.timeout, workers=args.workers,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for res in report.open_ports:
        line = f"{res.host:<39} {res.port:>5}/tcp  open"
        if res.banner:
            line += f"  {res.banner}"
        print(line)
        record(Finding(
            module="scan", target=f"{res.host}:{res.port}",
            title=f"Open port {res.port}/tcp", severity="info",
            detail=res.banner,
        ))
    print(
        f"-- {len(report.hosts_up)} host(s) up, "
        f"{report.open_count} open port(s), "
        f"{len(report.targets) * len(report.ports)} probes"
    )
    return 0 if report.open_count else 1


# --- web -------------------------------------------------------------------

def cmd_web(args: argparse.Namespace) -> int:
    from .modules import websec

    scope = load_scope()
    _require_scope(scope)
    url = args.url if "://" in args.url else "https://" + args.url
    try:
        report = websec.audit(
            url, scope, timeout=args.timeout, probe_paths=not args.no_paths,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"{report.final_url} -> HTTP {report.status}")
    for hdr in report.missing_headers:
        print(f"  missing header: {hdr}")
    for name, value in report.disclosures.items():
        print(f"  discloses {name}: {value}")
    for issue in report.cookie_issues:
        print(f"  cookie: {issue}")
    for path, status in report.exposed_paths.items():
        print(f"  exposed: {path} ({status})")
    if not report.findings:
        print("  no findings")

    for f in report.findings:
        record(Finding(module="web", target=f["target"], title=f["title"],
                       severity=f["severity"], detail=f["detail"]))
    return 0 if not any(
        f["severity"] in ("medium", "high", "critical") for f in report.findings
    ) else 1


# --- report ----------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    if args.clear:
        clear_findings()
        print("findings cleared")
        return 0
    findings = load_findings()
    if not findings:
        print("no findings recorded")
        return 0
    by_target: dict = {}
    for f in findings:
        by_target.setdefault(f.target, []).append(f)
    print(f"{len(findings)} finding(s) across {len(by_target)} target(s)\n")
    for target, items in sorted(by_target.items()):
        print(target)
        for f in items:
            print(f"  [{f.severity:<8}] {f.title}" + (f" - {f.detail}" if f.detail else ""))
        print()
    counts: dict = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    print("totals: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


# --- selftest --------------------------------------------------------------

def cmd_selftest(args: argparse.Namespace) -> int:
    from .modules import scan as scan_mod
    from .modules import websec

    failures: List[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'ok ' if ok else 'FAIL'} {name}" + (f" - {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    print("redkit selftest")
    check("version", __version__ == "0.1.0", __version__)
    try:
        ports = scan_mod.parse_ports("22,80,8000-8002")
        check("parse_ports", ports == [22, 80, 8000, 8001, 8002], str(ports))
    except ValueError as exc:
        check("parse_ports", False, str(exc))
    try:
        hosts = scan_mod.parse_targets("192.168.56.0/30")
        check("parse_targets cidr", len(hosts) == 2, str(hosts))
    except ValueError as exc:
        check("parse_targets cidr", False, str(exc))
    try:
        scan_mod.parse_targets("10.0.0.0/8")
        check("big-cidr refused", False, "should have raised")
    except ValueError:
        check("big-cidr refused", True)
    scope = Scope(["192.168.1.0/24", "example.com"])
    check("scope allows ip", scope.allows("192.168.1.77"))
    check("scope allows subdomain", scope.allows("https://app.example.com/x"))
    check("scope blocks stranger ip", not scope.allows("8.8.8.8"))
    check("scope blocks stranger domain", not scope.allows("https://notexample.com/"))
    blocked = False
    try:
        Scope([]).require("192.168.1.1")
    except OutOfScope:
        blocked = True
    check("empty scope refuses", blocked)
    check("probe localhost resolves",
          isinstance(socket.getaddrinfo("localhost", None), list))
    try:
        import ssl as _ssl
        websec._fetch  # attribute exists
        check("websec import", True)
    except Exception as exc:  # pragma: no cover
        check("websec import", False, str(exc))

    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


# --- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redkit",
        description="Scope-guarded offensive security toolkit for authorized tests.",
    )
    parser.add_argument("--version", action="version", version=f"redkit {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_scope = sub.add_parser("scope", help="manage authorized targets")
    scope_sub = p_scope.add_subparsers(dest="scope_cmd", required=True)
    for name in ("add", "remove"):
        p = scope_sub.add_parser(name)
        p.add_argument("entries", nargs="+", help="ip, cidr or domain")
    scope_sub.add_parser("list", help="print scope entries")
    scope_sub.add_parser("show", help="print scope file path")
    p_scope.set_defaults(func=cmd_scope)

    p_scan = sub.add_parser("scan", help="TCP connect scan (scope-gated)")
    p_scan.add_argument("targets", help="ip, cidr (max /24), or comma list")
    p_scan.add_argument("-p", "--ports", default=DEFAULT_SCAN_PORTS,
                        help="port list/ranges, e.g. 22,80,8000-8100")
    p_scan.add_argument("-t", "--timeout", type=float, default=1.0)
    p_scan.add_argument("-w", "--workers", type=int, default=64)
    p_scan.set_defaults(func=cmd_scan)

    p_web = sub.add_parser("web", help="security header audit (scope-gated)")
    p_web.add_argument("url", help="url or host (https assumed)")
    p_web.add_argument("-t", "--timeout", type=float, default=6.0)
    p_web.add_argument("--no-paths", action="store_true",
                       help="skip misconfiguration path probes")
    p_web.set_defaults(func=cmd_web)

    p_report = sub.add_parser("report", help="summarize stored findings")
    p_report.add_argument("--clear", action="store_true", help="delete stored findings")
    p_report.set_defaults(func=cmd_report)

    p_self = sub.add_parser("selftest", help="run built-in checks (no network)")
    p_self.set_defaults(func=cmd_selftest)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except OutOfScope as exc:
        print(f"refused: {exc}", file=sys.stderr)
        print("Only test systems you own or have written permission to test.",
              file=sys.stderr)
        return 3
    except EmptyScope as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    except ScopeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
