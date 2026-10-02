# E.I.S. Core — User Guide

Everything you need to install and use E.I.S. Core on another computer — no programming
experience required.

---

## Part 1 — Install on any computer

### What you need

| Requirement | Details |
|---|---|
| Computer | Windows 10 or 11 (64-bit). Runs fine on old/low-end PCs and HDDs. |
| Python | Version 3.10 or newer — free from [python.org/downloads](https://www.python.org/downloads/) |
| Disk space | About 30 MB |
| Internet | Only for downloading Python and updates — E.I.S. Core itself works offline |
| Optional | `psutil` (richer CPU/RAM data), Android *platform-tools* (ADB/Fastboot) |

### Step 1 — Install Python (one time)

1. Open <https://www.python.org/downloads/> in your browser and click the big yellow
   **Download Python** button.
2. Run the downloaded installer. **Important:** on the first screen, tick the checkbox
   **“Add python.exe to PATH”** at the bottom, then click *Install Now*.
3. When it finishes, click *Close*.

Check it worked: press **Win + R**, type `cmd`, press Enter, then type:

```bat
python --version
```

You should see something like `Python 3.13.1`. If you see “not recognized”, redo step 2 and make
sure the PATH checkbox is ticked.

### Step 2 — Get E.I.S. Core

**Option A — download a ZIP (easiest):**
1. On the GitHub project page, click the green **Code** button → **Download ZIP**.
2. Right-click the downloaded ZIP → *Extract All* → choose a simple location such as `C:\EISTech`.

**Option B — clone with Git (for updates):**

```bat
git clone https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git C:\EISTech
```

> **Portable option:** you can also extract the folder onto a USB stick and run it from there —
> all data stays inside the folder.

### Step 3 — Run it

Open the E.I.S. Core folder and double-click **`EIS-Core.bat`**.

That’s it — the dashboard opens. (If you prefer a terminal, `cd` into the folder and run
`python __main__.py`.)

### Optional extras

- **Better hardware stats** — in the terminal: `pip install psutil`
- **Android tools** — download
  [platform-tools](https://developer.android.com/tools/releases/platform-tools), extract it, then
  in E.I.S. Core go to **Settings → Android** and set the path.

---

## Part 2 — Using the dashboard

The left sidebar switches between the eight sections. **F1–F8** jump directly; **F5** refreshes
the current section.

### 🔧 System
Click **Refresh** to load a full inventory: CPU, RAM, GPU, motherboard, BIOS, drives, OS and
uptime. The CPU/RAM monitors update live. The storage analyzer shows every drive with capacity
and free space; the health checker reads SMART data when the drive exposes it.

### 🩺 Diagnostics
- **Event logs** — filter Windows errors/warnings/criticals to diagnose crashes.
- **Processes** — see what’s eating CPU or RAM; identify unknown executables by path.
- **Startup & Apps** — see what launches with Windows and what’s installed. Uninstall actions
  always ask for confirmation and use the Windows uninstaller.
- **Services / Firewall / Defender / Restore points** — status centers for the health of Windows
  itself. E.I.S. Core never turns your protection off.

### 🛠️ Repair
- **SFC / DISM** — the standard Windows file-repair tools, with live output and logs. These need
  administrator rights; E.I.S. Core asks Windows to elevate only when you start them.
- **DNS flush** — quick fix for “internet broken but connected” problems.
- **Temp cleaner** — shows how much space is recoverable before you confirm.
- **Network reset** — last-resort repair for broken network stacks; asks for explicit
  confirmation and explains what it does.

### 🤖 Android
Plug a phone in with USB debugging enabled and click **Detect**. You get device info, safe
presets (battery, reboot, screenshots), an APK analyzer, package manager, backup assistant and a
live logcat viewer with filters and export. The safety engine blocks dangerous commands (rooting,
bootloader unlock) — that is intentional.

### 🌐 Network
Adapters with IP/MAC/DNS at a glance. Ping with packet-loss history, DNS lookups, one-click
layered connectivity test (gateway → DNS → internet), Wi-Fi details, port checks against any
host, and passive local discovery of devices on your LAN.

### 📁 Files
- **Hashing** — verify a download or ISO against its published MD5/SHA-256.
- **Duplicate finder** — pick a folder (e.g. `D:\Downloads`); it never touches Windows or Program
  Files. Review the list, optionally delete extras — always with confirmation.
- **Password generator** — cryptographically secure passwords/passphrases.
- **QR payloads** — Wi-Fi, URL, text or contact-card payloads to share.

### 📚 Knowledge
Type an error message or symptom (e.g. “BOOT_DEVICE_NOT_FOUND”, “no display”, “0x80070005”) and
get matching causes, diagnostic steps and solutions from the built-in KB. You can add your own
entries — they stay in your database.

### 🗄️ Your data (customers, devices, jobs)
Use the Knowledge/Settings area to open the workspace tools:
1. Add a **customer**, then their **device**, then a **job** for what you’re fixing.
2. Add notes as you diagnose; every command you run is recorded in history automatically.
3. Generate a **report** (TXT/JSON/HTML) from a job to hand to the customer.
4. Use **Backup** before major work — it copies the database to `data/backups/`.

### ⚙️ Settings
Theme (dark/light), font size, logging, safety confirmations, tool defaults and paths. Settings
live in `data/settings.json`; a broken file resets to defaults automatically — your customer
database (`data/eis.db`) is never touched by settings.

---

## Part 3 — Good to know

| Question | Answer |
|---|---|
| Where is my data? | In the `data/` folder next to the app. Copy `data/eis.db` to back up everything. |
| Does it need admin? | Not for most tools. SFC/DISM/restore points ask via the Windows UAC prompt. |
| Does it phone home? | Never. No telemetry, no accounts. Only tools you explicitly run touch the network. |
| Can I use it at a repair shop? | Yes — that’s the point. MIT licensed, free for commercial use. |
| Something broke? | See [TROUBLESHOOTING.md](TROUBLESHOOTING.md), then check `data/logs/`. |
| Updating? | Re-download the ZIP and replace the folder, keeping your `data/` folder (or `git pull`). |
