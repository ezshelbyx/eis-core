# Changelog

All notable changes to E.I.S. Core are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/); versioning follows
[SemVer](https://semver.org/).

## [0.1.0] - 2026-10-02

First public release.

### Added
- Dashboard shell with 8 sections: System, Diagnostics, Repair, Android, Network, Files,
  Knowledge, Settings; dark/light theme engine; thread-safe result pump.
- **System:** CPU/RAM/GPU/motherboard/BIOS/storage/OS/uptime viewer, hardware scanner, live RAM
  and CPU monitors, storage analyzer, SMART/storage health checker.
- **Diagnostics:** event-log viewer with severity filtering, process manager, installed apps
  manager with safe uninstall shortcuts, startup manager, services manager, firewall / Defender /
  restore-point status centers.
- **Repair:** SFC and DISM centers with progress and logs, DNS cache flush, temp-file cleaner with
  recoverable-space estimate, network reset center with confirmation.
- **Android:** ADB/Fastboot detection, device info, curated command presets plus safety-gated
  manual console, APK analyzer, package manager, backup assistant, logcat viewer with
  filter/search/pause/export.
- **Network:** adapter viewer, ping with history, DNS diagnostics, layered connectivity tests,
  Wi-Fi info, port tester, non-invasive local discovery.
- **Files:** multi-algorithm hashing with verification, guarded duplicate finder, metadata
  inspector, CSPRNG password/passphrase generator, QR payloads.
- **Knowledge:** searchable troubleshooting KB with causes/diagnostics/solutions, custom entries,
  helpfulness feedback.
- **Workspace:** SQLite database (customers, devices, jobs, notes, command history), report
  generator (TXT/JSON/HTML), settings center.
- **Safety engine:** command classification (read/state/destructive/blocked), blocked patterns,
  protected-directory guards, confirmation gates, privilege-on-demand elevation.
- 150-test automated suite; full documentation set.
