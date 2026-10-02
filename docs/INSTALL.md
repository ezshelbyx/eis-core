# Installing E.I.S. Core

## 1. Install Python

1. Download Python **3.10 or newer** (3.13 recommended) from
   [python.org/downloads](https://www.python.org/downloads/).
2. Run the installer and **tick “Add python.exe to PATH”**.
3. Keep the default *tcl/tk and IDLE* component enabled — it provides **Tkinter**, which E.I.S.
   Core uses for its dashboard.
4. Verify from a terminal:

   ```bat
   python --version
   python -c "import tkinter; print('tkinter OK')"
   ```

## 2. Get E.I.S. Core

Either clone the repository (recommended for contributors):

```bat
git clone <repository-url> EISTech
cd EISTech
```

…or download and extract a release ZIP — E.I.S. Core is fully portable and needs no build step.

## 3. Optional components

| Component | Purpose | Install |
|---|---|---|
| `psutil` | Richer CPU/RAM/process telemetry | `pip install psutil` |
| Android platform-tools | ADB/Fastboot device servicing | Download from
  [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools),
  extract anywhere, then set `android.adb_path` / `android.fastboot_path` in **Settings**, or add
  the folder to `PATH` for auto-detection |
| `pytest` | Running the development test suite | `pip install pytest` |

Everything else uses the Python standard library — no other packages are required.

## 4. First run

From the project folder:

```bat
python __main__.py
```

or double-click **`EIS-Core.bat`**.

On first start E.I.S. Core creates its workspace next to the code:

```
data/
├── eis.db                      # technician database (customers, devices, jobs, notes, history)
├── settings.json               # application settings (safe to edit; validated on load)
├── logs/                       # application log + command_history.jsonl
├── reports/                    # generated TXT/JSON/HTML reports
├── backups/                    # database backups
├── exports/                    # KB exports, logcat exports
└── downloads/                  # APK backups and similar artifacts
```

> **Portable note:** the whole project folder can live on a USB drive. All state stays inside
> `data/`; nothing is written to the registry or outside the workspace.

## 5. Administrator rights

Most tools work unprivileged. A handful (SFC, DISM, some service operations, restore-point
creation) require elevation — E.I.S. Core detects this and asks only when the specific action
needs it. See [SECURITY.md](SECURITY.md) for how privilege requests are handled.

## 6. Verify the installation

Run the automated test suite:

```bat
python -m pytest tests/ -q
```

Expected result: **150 passed** (a few tests are Windows-only and skip gracefully elsewhere).

## 7. Uninstall

E.I.S. Core has no installer — delete the project folder. To keep your customer database, copy
`data/eis.db` (and optionally `data/` as a whole) somewhere safe first.
