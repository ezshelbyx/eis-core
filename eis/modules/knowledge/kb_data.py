"""Built-in troubleshooting knowledge base entries.

Each entry connects symptoms/errors with causes, diagnostics and solutions.
Custom entries live in ``data/kb_custom.json`` (see kb.py) and are merged
with this pack at runtime.

Schema
------
id: stable identifier (string)
title, category, os, severity: display metadata
symptoms: list of user-describable symptoms (matched against searches)
error_patterns: substrings/regex-ish markers found in logs or messages
causes: list of likely root causes
diagnostics: ordered checks to run (may reference E.I.S. tools)
solutions: ordered fixes, safest first
references: optional URLs or doc pointers
"""

from __future__ import annotations

ENTRIES: list[dict] = [
    {
        "id": "kb-0001-bsod-memory",
        "title": "Random Blue Screens with MEMORY_MANAGEMENT / IRQL_NOT_LESS_OR_EQUAL",
        "category": "Hardware",
        "os": "Windows",
        "severity": "critical",
        "symptoms": [
            "blue screen", "bsod", "random crash", "reboots by itself",
            "MEMORY_MANAGEMENT", "IRQL_NOT_LESS_OR_EQUAL",
        ],
        "error_patterns": ["MEMORY_MANAGEMENT", "IRQL_NOT_LESS_OR_EQUAL", "PAGE_FAULT_IN_NONPAGED_AREA"],
        "causes": [
            "Faulty RAM module or wrong XMP/DOCP profile",
            "Bad driver writing to freed memory",
            "Overheating memory controller or CPU",
        ],
        "diagnostics": [
            "Run Windows Memory Diagnostic (mdsched.exe) or MemTest86 overnight",
            "E.I.S. > System > RAM monitor: watch for ECC/errors if reported",
            "Check Event Viewer for WHEA-Logger errors",
            "Reset BIOS to defaults; disable XMP and test again",
        ],
        "solutions": [
            "Test RAM sticks one at a time to isolate the faulty module",
            "Reseat memory and clean contacts with isopropyl alcohol",
            "Update chipset and storage drivers",
            "Replace the faulty module",
        ],
        "references": ["https://learn.microsoft.com/windows-hardware/drivers/debugger/bug-check-code-reference2"],
    },
    {
        "id": "kb-0002-slow-boot",
        "title": "Very slow Windows boot / desktop takes minutes to load",
        "category": "Performance",
        "os": "Windows",
        "severity": "high",
        "symptoms": ["slow boot", "takes forever to start", "spinning dots", "black screen after login"],
        "error_patterns": ["Event 100", "Boot perf", "service timeout"],
        "causes": [
            "Failing HDD (check SMART) - very common on old laptops",
            "Too many startup programs",
            "Pending Windows Updates stuck in installation",
            "Failing system files",
        ],
        "diagnostics": [
            "E.I.S. > System > Storage health: look for 'Warning'/'Unhealthy' SMART status",
            "E.I.S. > Windows > Startup manager: count enabled entries",
            "Event Viewer > Applications and Services > Microsoft > Windows > Diagnostics-Performance",
        ],
        "solutions": [
            "If HDD SMART is failing: back up NOW and replace with SSD",
            "Trim startup programs via Task Manager > Startup apps",
            "Run SFC /SCANNOW then DISM /Online /Cleanup-Image /RestoreHealth",
            "Install pending updates and reboot twice",
        ],
        "references": [],
    },
    {
        "id": "kb-0003-no-internet",
        "title": "No internet access but Wi-Fi shows connected",
        "category": "Network",
        "os": "Any",
        "severity": "high",
        "symptoms": ["no internet", "connected but no internet", "yellow triangle", "cannot browse"],
        "error_patterns": ["DNS_PROBE_FINISHED_NO_INTERNET", "ERR_INTERNET_DISCONNECTED", "gateway unreachable"],
        "causes": [
            "Router lost WAN (ISP outage)",
            "DNS server unreachable or hijacked",
            "Static IP configured by mistake",
            "VPN or proxy still active",
        ],
        "diagnostics": [
            "E.I.S. > Network > Connectivity: run the gateway/DNS/Internet test",
            "Ping the default gateway (Network > Ping)",
            "Try resolving a name: Network > DNS lookup",
        ],
        "solutions": [
            "Gateway unreachable: reboot router, check cables, forget/rejoin Wi-Fi",
            "Gateway OK but DNS fails: set DNS to 1.1.1.1/8.8.8.8, then flush DNS cache",
            "Run E.I.S. > Network > DNS flush",
            "Last resort: Network reset (Settings > Network > Reset) and restart",
        ],
        "references": [],
    },
    {
        "id": "kb-0004-wifi-drops",
        "title": "Wi-Fi keeps disconnecting or speed is unstable",
        "category": "Network",
        "os": "Windows",
        "severity": "medium",
        "symptoms": ["wifi drops", "keeps disconnecting", "slow wifi", "unstable connection"],
        "error_patterns": ["WLAN-AutoConfig", "Event 8003", "beacon loss"],
        "causes": [
            "Channel congestion (2.4 GHz in apartment blocks)",
            "Outdated Wi-Fi driver or power saving killing the adapter",
            "Router too far / 5 GHz signal too weak",
        ],
        "diagnostics": [
            "E.I.S. > Network > Wi-Fi info: check signal % and channel",
            "Nearby networks scan: look for overlapping channels",
        ],
        "solutions": [
            "Disable 'Allow the computer to turn off this device' in adapter power management",
            "Force 5 GHz preferred band in adapter advanced settings",
            "Change router to a clean channel (1/6/11 on 2.4 GHz)",
            "Update the wireless driver from the vendor site",
        ],
        "references": [],
    },
    {
        "id": "kb-0005-disk-full",
        "title": "C: drive almost full, Windows sluggish",
        "category": "Storage",
        "os": "Windows",
        "severity": "high",
        "symptoms": ["disk full", "low space", "c drive red", "out of storage"],
        "error_patterns": ["Low Disk Space", "0x80070070", "ERROR_DISK_FULL"],
        "causes": [
            "Temporary files and update cache buildup",
            "Hibernation file and old restore points",
            "Browser caches and duplicate downloads",
        ],
        "diagnostics": [
            "E.I.S. > System > Storage analyzer: check free space",
            "E.I.S. > Windows > Temp cleaner: estimate recoverable GB",
            "E.I.S. > Files > Duplicate finder on user folders",
        ],
        "solutions": [
            "Run the Temp cleaner with Windows Update cache included",
            "Disk Cleanup > Clean up system files (Windows Update cleanup)",
            "Move large media to another drive or cloud",
            "Compact hibernation: powercfg /h /size 50 (admin)",
        ],
        "references": [],
    },
    {
        "id": "kb-0006-usb-not-recognized",
        "title": "USB device not recognized / keeps reconnecting",
        "category": "Hardware",
        "os": "Windows",
        "severity": "medium",
        "symptoms": ["usb not recognized", "device descriptor failed", "usb disconnects"],
        "error_patterns": ["Unknown USB Device", "Device Descriptor Request Failed", "Code 43"],
        "causes": [
            "Failing cable/connector (most common)",
            "Insufficient power on the port",
            "Corrupt driver for the device",
        ],
        "diagnostics": [
            "E.I.S. > System > Hardware scanner: look for problem devices",
            "Try another port (prefer rear/motherboard ports on desktops)",
        ],
        "solutions": [
            "Replace the cable first",
            "Uninstall the device in Device Manager and rescan",
            "Disable USB selective suspend in power plan",
            "Chipset drivers update",
        ],
        "references": [],
    },
    {
        "id": "kb-0007-phone-not-detected",
        "title": "Android phone not detected by PC / ADB",
        "category": "Android",
        "os": "Any",
        "severity": "low",
        "symptoms": ["phone not detected", "adb devices empty", "usb debugging not showing"],
        "error_patterns": ["unauthorized", "no devices", "offline device"],
        "causes": [
            "USB debugging disabled",
            "Authorization prompt pending/missed on the phone",
            "Cable is charge-only",
            "Driver missing on Windows",
        ],
        "diagnostics": [
            "E.I.S. > Android: click Detect - read the error text",
            "Check phone notification USB mode = File transfer",
        ],
        "solutions": [
            "Enable Developer options > USB debugging",
            "Accept the RSA fingerprint dialog on the phone",
            "Use a data cable, try another port",
            "Install OEM USB driver, restart ADB (adb kill-server; adb start-server)",
        ],
        "references": [],
    },
    {
        "id": "kb-0008-high-cpu",
        "title": "CPU at 100% and laptop overheats / throttles",
        "category": "Performance",
        "os": "Windows",
        "severity": "medium",
        "symptoms": ["high cpu", "fan loud", "laptop hot", "slow after minutes"],
        "error_patterns": ["WHEA Thermal", "Kernel-Power 41"],
        "causes": [
            "Background updater/miner malware",
            "Dust-clogged heatsink (thermal paste dried)",
            "Runaway browser tab or antivirus scan storm",
        ],
        "diagnostics": [
            "E.I.S. > System > CPU monitor: identify sustained load",
            "E.I.S. > Windows > Processes: sort by CPU",
            "Check CPU temperature if sensors are exposed",
        ],
        "solutions": [
            "End unknown high-CPU processes after verifying their path",
            "Clean fans/heatsink, replace thermal paste (hardware service)",
            "Full antivirus scan",
            "Limit startup apps and browser extensions",
        ],
        "references": [],
    },
    {
        "id": "kb-0009-corrupt-system",
        "title": "Windows Update fails with corrupt component store errors",
        "category": "System repair",
        "os": "Windows",
        "severity": "high",
        "symptoms": ["update fails", "stuck at percent", "0x800f0922", "component store corrupt"],
        "error_patterns": ["0x800f0922", "0x80073712", "CBS", "corruption"],
        "causes": [
            "Component store corruption",
            "Disk errors on system volume",
            "Third-party antivirus blocking the update service",
        ],
        "diagnostics": [
            "E.I.S. > Windows > DISM center: run CheckHealth then ScanHealth",
            "chkdsk C: /scan (read-only check)",
        ],
        "solutions": [
            "DISM /Online /Cleanup-Image /RestoreHealth (admin)",
            "Then SFC /SCANNOW",
            "Retry Windows Update after reboot",
            "As last resort: in-place upgrade repair install",
        ],
        "references": ["https://learn.microsoft.com/windows/deployment/update/dism-reference"],
    },
    {
        "id": "kb-0010-suspect-malware",
        "title": "Suspected malware: unknown processes, popups, browser redirects",
        "category": "Security",
        "os": "Windows",
        "severity": "critical",
        "symptoms": ["virus", "malware", "popups", "browser redirect", "unknown process"],
        "error_patterns": [],
        "causes": [
            "Adware/PUP installed with bundled software",
            "Infected browser extension",
            "Malicious scheduled task or startup entry",
        ],
        "diagnostics": [
            "E.I.S. > Windows > Processes: check executable paths of unknown entries",
            "E.I.S. > Windows > Startup manager: spot suspicious entries",
            "E.I.S. > Windows > Defender status: confirm protection is ON",
        ],
        "solutions": [
            "Disconnect from network; run full Defender scan",
            "Remove unknown startup entries and browser extensions",
            "Create a restore point BEFORE deep cleaning (E.I.S. can help)",
            "If persists: boot Safe Mode, run second-opinion scanner",
        ],
        "references": [],
    },
    {
        "id": "kb-0011-printer-offline",
        "title": "Printer shows offline / jobs stuck in queue",
        "category": "Peripherals",
        "os": "Windows",
        "severity": "low",
        "symptoms": ["printer offline", "stuck queue", "cannot print"],
        "error_patterns": ["Print Spooler", "0x0000011b"],
        "causes": [
            "Spooler service crashed",
            "Printer changed IP (DHCP) - port points to old address",
            "Driver mismatch after update",
        ],
        "diagnostics": [
            "E.I.S. > Windows > Services: check 'Spooler' status",
            "Ping the printer's IP (Network > Ping)",
        ],
        "solutions": [
            "Restart the Spooler service and clear the queue",
            "Set a DHCP reservation or static IP for the printer, recreate the port",
            "Reinstall the latest vendor driver",
        ],
        "references": [],
    },
    {
        "id": "kb-0012-apk-risky",
        "title": "Customer sideloaded an APK and phone behaves oddly (ads, data usage)",
        "category": "Android",
        "os": "Android",
        "severity": "medium",
        "symptoms": ["sideloaded app ads", "high data usage", "unknown app", "battery drains fast"],
        "error_patterns": ["REQUEST_INSTALL_PACKAGES", "QUERY_ALL_PACKAGES"],
        "causes": [
            "Repackaged APK with adware",
            "App requests excessive permissions",
        ],
        "diagnostics": [
            "E.I.S. > Android > APK analyzer: inspect the APK before install",
            "Review 'risky permissions' list - SMS/location/accessibility combos are red flags",
        ],
        "solutions": [
            "Uninstall the suspicious package (Android > Package manager)",
            "Install the app only from the official store",
            "Revoke device-admin rights for unknown apps first",
            "Factory reset if the device-admin cannot be removed",
        ],
        "references": [],
    },
]
