# Troubleshooting

Common problems, their causes and fixes. If your problem is not listed, please open an issue
(see [CONTRIBUTING.md](CONTRIBUTING.md)) with the log from `data/logs/`.

## Startup problems

### `ModuleNotFoundError: No module named 'eis'`
You launched from a different folder. `cd` into the project root (the folder containing
`__main__.py`) and run `python __main__.py`.

### `ImportError: DLL load failed … tkinter` or `_tkinter` missing
Your Python build lacks Tk. Reinstall Python from python.org and keep the **tcl/tk and IDLE**
component enabled, or use the full installer instead of the embeddable package.

### Window opens but looks unstyled / tiny
Tk scaling differs across DPI settings. Try Settings → appearance → font size; the geometry and
maximized flag are stored in `data/settings.json` and can be edited by hand (values are
validated on load).

### App was closed uncleanly and now complains
Delete only `data/settings.json` to reset settings to factory defaults — **not** `data/eis.db`,
which holds your customer data.

## Diagnostics & repair

### SFC/DISM says it needs administrator rights
These Windows tools genuinely require elevation. E.I.S. Core asks for elevation when you start
the repair; accept the UAC prompt. Nothing else in E.I.S. runs elevated.

### CPU temperature shows “n/a”
Temperature is only available when the hardware exposes it to Windows (most laptops do not,
without vendor drivers). E.I.S. Core shows what the OS reports and hides the rest.

### SMART attributes missing
Windows may not surface SMART for USB/SATA bridges. Try the drive directly on SATA; external
enclosures often strip SMART passthrough.

### psutil-related features show reduced detail
Install the optional package: `pip install psutil`. E.I.S. Core works without it, just with less
granular CPU/RAM/process data.

## Android

### “ADB not found”
Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools),
then either add the folder to `PATH` or set the full path in Settings → Android
(`android.adb_path`). The ADB detector re-runs on every device scan.

### Device detected but not authorized
Look at the phone: accept the “Allow USB debugging” prompt for this computer. If it never
appears, revoke USB debugging authorizations on the device and reconnect.

### Device shows in fastboot, not in ADB (or vice versa)
That is normal — fastboot and ADB are different modes with different drivers. E.I.S. Core shows
both detectors; install the matching driver if Windows marks the device with an error.

### The manual console refused my command
The safety engine blocks irreversibly dangerous commands (`adb shell su`, bootloader unlock,
forced reboot variants, …) and requires confirmation for state-changing ones. Blocked patterns
are not configurable by design.

## Network

### Ping says “transmit failed” but the website works
Some routers drop ICMP. Use the connectivity diagnostic (gateway → DNS → external) for a fuller
picture, or test the specific TCP port with the port tool.

### Local discovery finds fewer devices than expected
Discovery is deliberately passive/non-invasive; devices that block ARP/netbios probes stay
invisible. It is a discovery aid, not an audit tool.

### Wi-Fi section is empty
The underlying `netsh wlan` interface requires a Wi-Fi adapter (USB dongles count). Ethernet-only
systems legitimately have nothing to show.

## Files

### Duplicate finder refuses a folder with “protected system/user directory”
By design: scans and deletions are refused inside Windows, Program Files, ProgramData, user
profile folders (Documents, Desktop, Pictures, AppData) and drive roots. Pick a starting folder
below those, e.g. `D:\Projects`.

### Hash mismatch on a file you did not modify
Line-ending conversion or a partial copy often changes content. Re-copy the file in binary mode
and compare again; the metadata inspector shows both timestamps and hashes to spot such cases.

## Database

### “database is locked”
Close other E.I.S. Core instances (the UI and any script sharing `data/eis.db`). WAL mode allows
multiple readers; only one writer at a time.

### Recovering / moving your data
Stop the app, copy `data/eis.db`, and use Database → backup to create a timestamped copy in
`data/backups/` before risky operations.

## Tests

### `test_powershell_runs` times out
First-run PowerShell cold start can take a while on HDD machines; the test allows 90 s. If it
still times out, run `powershell -NoProfile -Command "echo ok"` manually to check PowerShell
health.

### Duplicate-finder tests fail on unusual setups
The tests use pytest `tmp_path` with a permissive stand-in safety engine. If you changed
`eis/core/safety.py` guard signatures, update `_AllowScanRoots` in `tests/test_files_tools.py`.
