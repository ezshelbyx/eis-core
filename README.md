# redkit

**Scope-guarded offensive security toolkit for authorized penetration tests — built to run in Kali NetHunter on an Android phone.**

Pure Python standard library. No pip, no dependencies, no build step. Copy the folder into your NetHunter Kali chroot and run it.

```
███    ██ ███████ ██    ██ ███████
████   ██ ██       ██  ██  ██
██ ██  ██ █████     ████   █████
██  ██ ██ ██         ██    ██
██   ████ ███████    ██    ███████
```

## Authorization required

This is a penetration-testing toolkit. **Only run it against systems you own or have written permission to test.** That means your home lab, your own devices, your own network — or a client engagement with a signed scope of work.

redkit enforces this technically, not just morally: every network command reads a **scope file** first, and refuses any target you have not explicitly authorized — before a single packet leaves your phone.

- Empty scope → every scan and web audit is refused (exit code 3).
- Out-of-scope target → refused, with a reminder about written permission.
- Scope never touches the network — checking a target costs nothing.

There is no `--force`, no `--i-know-what-im-doing`, no bypass flag. Adding a target to the scope *is* the authorization step.

## Running on a NetHunter phone

Python runs inside the **Kali chroot**, not Termux. Verified flow:

1. Open the **NetHunter app** → **Kali Chroot Manager** → make sure a chroot is installed.
2. Open **NetHunter Terminal** and pick the **Kali** session (not *Android* / *AndroidSu*).
3. Copy this folder somewhere in the chroot:

```sh
# from Android storage, if the terminal can read it:
mkdir -p ~/tools
cp -r /sdcard/Download/redkit ~/tools/
cd ~/tools/redkit
```

If `/sdcard/...` is not readable, enable "Allow access to manage all files" for NetHunter Terminal in Android settings.

4. Check Python and run:

```sh
command -v python3 || (apt update && apt install -y python3)
python3 -m redkit --version
python3 -m redkit selftest
```

`python3 -m redkit` works from the repo root with **zero installation**. If you want the short `redkit` command instead: `pip install .` (or `pip install --break-system-packages .` on newer Kali), but stdlib-direct is recommended — Kali discourages system-wide pip installs.

Storage note: scope and findings live in `~/.redkit/` **inside the chroot**, so they survive `/sdcard` quirks. Override with `REDKIT_HOME=/path` if needed.

## Quick start

```sh
# 1. Authorize your targets (this is the permission step)
python3 -m redkit scope add 192.168.1.0/24          # your LAN
python3 -m redkit scope add example.com             # a client domain
python3 -m redkit scope list

# 2. Port-scan an authorized host
python3 -m redkit scan 192.168.1.10
python3 -m redkit scan 192.168.1.10 -p 22,80,443,8000-8100
python3 -m redkit scan 192.168.1.0/24 -p 445,3389 -t 0.5 -w 128

# 3. Audit a website's hardening headers
python3 -m redkit web https://example.com
python3 -m redkit web https://example.com --no-paths

# 4. Review everything you've found
python3 -m redkit report
python3 -m redkit report --clear    # start a fresh engagement
```

Example scan output:

```
192.168.1.10                               22/tcp  open  SSH-2.0-OpenSSH_9.6
192.168.1.10                              443/tcp  open
-- 1 host(s) up, 2 open port(s), 16 probes
```

## Commands

| Command | What it does |
|---|---|
| `scope add\|remove\|list\|show` | Manage authorized targets (IPs, CIDRs up to /24, domains incl. `*.wildcard`) |
| `scan <targets> -p <ports>` | TCP connect scan with banner grabbing. Threaded, timeout/worker tunable. Max /24 per scan. |
| `web <url>` | Security header audit: missing hardening headers, server disclosure, insecure cookies, exposed paths (`.git/HEAD`, `.env`, `/server-status`, ...). |
| `report [--clear]` | Summarize recorded findings by target with severity totals |
| `selftest` | Built-in checks, no network needed — good first command on a new phone |

Exit codes: `0` success · `1` findings (scan/web) · `2` bad usage · `3` refused (out of scope / empty scope).

## Design notes

- **Fail closed.** Scope checks happen before any DNS lookup or socket. If the scope file is unreadable, nothing runs.
- **Stdlib only.** `socket`, `ssl`, `urllib`, `argparse` — nothing to install, works in a minimal chroot.
- **Phone-friendly threading.** Connect scans default to 64 workers (cap: 256) to stay inside Android's file-descriptor limits; tune with `-w`.
- **Findings as JSON lines.** `$REDKIT_HOME/findings.jsonl` — one JSON object per line, greppable, append-safe, tolerant of partial lines.
- **No raw sockets needed.** A TCP connect scan works unprivileged, so it behaves the same in the Kali chroot whether or not you're root.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q      # 39 tests, all offline
```

Module layout:

```
redkit/
├── cli.py           # argparse subcommands, exit codes, refusal handling
├── scope.py         # authorization model (the heart of the tool)
├── store.py         # findings.jsonl read/write
└── modules/
    ├── scan.py      # port parse, threaded connect scan, banner grab
    └── websec.py    # header audit, cookie checks, path probes
```

Adding a module: put it in `redkit/modules/`, take `scope: Scope` as a parameter, call `scope.require(target)` first, record `Finding` objects via `store.record`, wire a subcommand in `cli.py`, add tests under `tests/`.

## Legal

MIT licensed (see `LICENSE`). The license covers the code, not your use of it. Scanning systems without authorization is a crime in most jurisdictions — including systems that are attacking you. If you're dealing with an active attacker, keep evidence (IPs, logs, timestamps), report it to your provider/platform, and talk to a lawyer or law enforcement rather than striking back. This tool is for testing what you're authorized to test.

## Roadmap

- TLS certificate inspection (expiry, chain, weak ciphers) in `web`
- `dns` module: zone-walk friendly record enumeration (in-scope only)
- JSON output flag (`--json`) for piping into other tooling
- Wordlist-driven content discovery beyond the fixed probe list
