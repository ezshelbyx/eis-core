"""Android section: device detection, info, command console, packages, logcat."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.ui.widgets import Card, KVTable, OutputConsole, Section, ToolBar


class AndroidView(Section):
    label = "Android"
    icon = "\U0001F4F1"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        bar = ToolBar(self)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Detect devices", self._detect, style="Accent.TButton", name="detect")
        self.device_label = ttk.Label(bar, text="No devices checked yet.", style="Dim.TLabel")
        self.device_label.pack(side="left", padx=10)
        self.serial_var = tk.StringVar(value="")
        self.serial_box = ttk.Combobox(bar, textvariable=self.serial_var, width=22, state="readonly")
        self.serial_box.pack(side="left")

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._build_info_tab(notebook)
        self._build_console_tab(notebook)
        self._build_packages_tab(notebook)
        self._build_logcat_tab(notebook)

    # -- detection -----------------------------------------------------------
    def _detect(self) -> None:
        self.status("Detecting ADB and connected devices...")
        self.run_in_thread(self._detect_job, self._detect_done)

    def _detect_job(self):
        from eis.modules.android.adb import adb_path, detect, list_fastboot_devices, fastboot_path

        return {
            "adb": adb_path(),
            "fastboot": fastboot_path(),
            "info": detect(),
        }

    def _detect_done(self, result) -> None:
        lines = [
            f"ADB     : {result['adb'] or 'NOT FOUND - install Android platform-tools and set the path in Settings'}",
            f"Fastboot: {result['fastboot'] or 'not found'}",
            "",
        ]
        devices = result["info"].get("devices", [])
        fb_devices = result["info"].get("fastboot_devices", [])
        if devices:
            lines.append(f"ADB devices: {len(devices)}")
            for d in devices:
                lines.append(f"  {d['serial']}  ({d['state']})")
        if fb_devices:
            lines.append(f"Fastboot devices: {len(fb_devices)}")
            for d in fb_devices:
                lines.append(f"  {d['serial']}")
        if not devices and not fb_devices:
            lines.append("No devices. Connect a phone with USB debugging enabled and accept the RSA prompt.")
        self.info_console.append("\n".join(lines))
        serials = [d["serial"] for d in devices]
        self.serial_box["values"] = serials or [""]
        if serials and not self.serial_var.get():
            self.serial_var.set(serials[0])
        self.device_label.configure(
            text=f"{len(devices)} ADB device(s), {len(fb_devices)} fastboot"
        )
        self.status("Android detection complete.")

    # -- device info ---------------------------------------------------------
    def _build_info_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Device info ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Read device info", self._read_info)
        self.info_table = KVTable(tab, height=18)
        self.info_table.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.info_console = None  # reuse parent console below

        # console lives on the detection bar area (simplest: attach to info tab bottom)
        self.info_output = OutputConsole(tab, height=6, save_name="adb_detection.txt")
        self.info_output.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.info_console = self.info_output

    def _read_info(self) -> None:
        serial = self.serial_var.get()
        self.status("Reading device properties...")
        self.run_in_thread(lambda: self._info_job(serial), self._info_done)

    def _info_job(self, serial: str):
        from eis.modules.android.adb import device_info

        return device_info(serial)

    def _info_done(self, info) -> None:
        if not info.get("ok"):
            self.info_output.append(f"Error: {info.get('error')}")
            if "unauthorized" in str(info.get("error", "")).lower():
                self.info("Unauthorized", "Accept the 'Allow USB debugging' dialog on the phone and retry.")
            return
        rows = [
            ("Model", info.get("model", "?")),
            ("Brand", info.get("brand", "?")),
            ("Manufacturer", info.get("manufacturer", "?")),
            ("Device", info.get("device", "?")),
            ("Android version", info.get("android_version", "?")),
            ("SDK", info.get("sdk", "?")),
            ("Build", info.get("build", "?")),
            ("Security patch", info.get("security_patch", "?")),
            ("Serial", info.get("serial", "?")),
            ("CPU ABI", info.get("cpu_abi", "?")),
            ("Hardware", info.get("hardware", "?")),
            ("Board", info.get("board", "?")),
            ("Battery level", info.get("battery_level", "?")),
            ("Battery status", info.get("battery_status", "?")),
            ("/data storage", f"{info.get('data_used', '?')} used, {info.get('data_free', '?')} free"),
        ]
        self.info_table.set_rows(rows)
        self.status("Device info loaded.")

    # -- console ---------------------------------------------------------------
    def _build_console_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        tab.rowconfigure(3, weight=1)
        parent.add(tab, text=" Command center ")

        ttk.Label(tab, text="Safe presets:", style="Dim.TLabel").grid(row=0, column=0, sticky="w")
        presets_row = ttk.Frame(tab)
        presets_row.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        for preset_id, label in (
            ("devices", "List devices"), ("info", "Props"), ("battery", "Battery"),
            ("storage", "Storage"), ("memory", "Memory"), ("packages3rd", "User apps"),
            ("wifilist", "Wi-Fi networks"), ("screencap", "Screenshot"),
        ):
            ttk.Button(presets_row, text=label,
                       command=lambda p=preset_id: self._run_preset(p)).pack(side="left", padx=(0, 4))

        manual_row = ttk.Frame(tab)
        manual_row.grid(row=2, column=0, sticky="ew")
        self.manual_var = tk.StringVar()
        ttk.Label(manual_row, text="adb").pack(side="left")
        entry = ttk.Entry(manual_row, textvariable=self.manual_var)
        entry.pack(side="left", fill="x", expand=True, padx=4)
        entry.bind("<Return>", lambda _e: self._run_manual())
        ttk.Button(manual_row, text="Run", command=self._run_manual, style="Accent.TButton").pack(side="left")
        ttk.Label(tab, text="Destructive commands are blocked or require confirmation. Type 'help' for hints.",
                  style="Dim.TLabel").grid(row=3, column=0, sticky="w")

        self.console = OutputConsole(tab, height=16, save_name="adb_console.txt")
        self.console.grid(row=4, column=0, sticky="nsew", pady=(6, 0))

    def _run_preset(self, preset_id: str) -> None:
        serial = self.serial_var.get()
        self.run_in_thread(lambda: self._preset_job(preset_id, serial), self._preset_done)

    def _preset_job(self, preset_id: str, serial: str):
        from eis.modules.android.console import run_preset

        return run_preset(preset_id, serial)

    def _preset_done(self, result) -> None:
        if result.get("confirm_required"):
            if self.confirm("Destructive command", result.get("label", "") + "\n\n" + "Run this command?"):
                self._run_manual_command(result.get("command", ""))
            return
        self.console.append(f"$ {result.get('command', '')}\n{result.get('output', result.get('error', ''))}\n")
        self.status(f"Preset '{result.get('label', '')}' done.")

    def _run_manual(self) -> None:
        cmd = self.manual_var.get().strip()
        if not cmd:
            return
        if cmd.lower() == "help":
            self.console.append(
                "Examples:\n"
                "  adb shell getprop ro.product.model\n"
                "  adb shell dumpsys battery\n"
                "  adb install -r app.apk\n"
                "  adb shell pm list packages -3\n"
                "Blocked: adb reboot bootloader, su/root commands, shell rm / ..."
            )
            return
        self._run_manual_command("adb " + cmd.removeprefix("adb "))

    def _run_manual_command(self, command: str) -> None:
        serial = self.serial_var.get()
        self.run_in_thread(lambda: self._manual_job(command, serial), self._manual_done)

    def _manual_job(self, command: str, serial: str):
        from eis.modules.android.console import run_manual

        return run_manual(command, serial)

    def _manual_done(self, result) -> None:
        if result.get("confirm_required"):
            if self.confirm("Destructive command", result.get("confirmation_text", "Run?")):
                self._run_manual_command_confirmed(result.get("command", ""))
            return
        self.console.append(f"$ {result.get('command', '')}\n{result.get('output', result.get('error', ''))}\n")
        self.status("Command finished." if result.get("ok") else "Command failed.")

    def _run_manual_command_confirmed(self, command: str) -> None:
        serial = self.serial_var.get()
        self.run_in_thread(lambda: self._confirmed_job(command, serial), self._manual_done)

    def _confirmed_job(self, command: str, serial: str):
        from eis.modules.android.console import run_manual

        return run_manual(command, serial, confirmed=True)

    # -- packages ----------------------------------------------------------------
    def _build_packages_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Packages ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.pkg_kind_var = tk.StringVar(value="3rd")
        ttk.Combobox(bar, textvariable=self.pkg_kind_var, width=10, state="readonly",
                     values=("3rd", "system", "all", "enabled", "disabled")).pack(side="left")
        bar.add_entry("pkg_search", width=24)
        bar.add_button("List", self._list_packages)
        bar.add_button("Disable", lambda: self._pkg_action("disable"), style="Danger.TButton")
        bar.add_button("Uninstall", lambda: self._pkg_action("uninstall"), style="Danger.TButton")
        bar.add_button("Backup APK", self._backup_apk, style="Accent.TButton")

        cols = ("package",)
        self.pkg_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        self.pkg_tree.heading("package", text="Package name")
        self.pkg_tree.column("package", width=700, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.pkg_tree.yview)
        self.pkg_tree.configure(yscrollcommand=vsb.set)
        self.pkg_tree.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        vsb.grid(row=2, column=1, sticky="ns")

    def _list_packages(self) -> None:
        kind = self.pkg_kind_var.get()
        serial = self.serial_var.get()
        search = self.pkg_tree.master.grid_slaves(row=0)[0].get("pkg_search")  # type: ignore[attr-defined]
        self.status(f"Listing {kind} packages...")
        self.run_in_thread(lambda: self._pkg_job(kind, serial, search), self._pkg_done)

    def _pkg_job(self, kind: str, serial: str, search: str):
        from eis.modules.android.packages import list_packages

        return list_packages(serial=serial, kind=kind, search=search)

    def _pkg_done(self, result) -> None:
        self.pkg_tree.delete(*self.pkg_tree.get_children())
        if not result.get("ok"):
            self.status(f"Package list failed: {result.get('error')}")
            return
        for name in result.get("packages", []):
            self.pkg_tree.insert("", "end", values=(name,))
        self.status(f"{result.get('count', 0)} packages.")

    def _selected_package(self) -> str:
        sel = self.pkg_tree.selection()
        if not sel:
            return ""
        return self.pkg_tree.item(sel[0], "values")[0]

    def _pkg_action(self, action: str) -> None:
        package = self._selected_package()
        if not package:
            self.info("Packages", "Select a package first.")
            return
        serial = self.serial_var.get()
        self.run_in_thread(lambda: self._action_job(package, action, serial), self._action_done)

    def _action_job(self, package: str, action: str, serial: str):
        from eis.modules.android.packages import change_package_state

        return change_package_state(package, action, serial=serial, confirmed=False)

    def _action_done(self, result) -> None:
        if result.get("confirm_required"):
            if self.confirm("Package action", result.get("warning", "")):
                package = self._selected_package()
                serial = self.serial_var.get()
                self.run_in_thread(
                    lambda: self._confirmed_action_job(package, result.get("_action", "disable"), serial),
                    self._pkg_action_final,
                )
            return
        self._pkg_action_final(result)

    def _confirmed_action_job(self, package: str, action: str, serial: str):
        from eis.modules.android.packages import change_package_state

        return change_package_state(package, action, serial=serial, confirmed=True)

    def _pkg_action_final(self, result) -> None:
        if result.get("ok"):
            self.status(f"Package {result.get('package')}: {result.get('action')} OK.")
            self.console.append(f"$ {result.get('output', '')}")
            self._list_packages()
        else:
            self.error("Package action", result.get("error") or result.get("output") or "Failed.")

    def _backup_apk(self) -> None:
        package = self._selected_package()
        if not package:
            self.info("Backup APK", "Select a package first.")
            return
        serial = self.serial_var.get()
        self.status(f"Pulling APK for {package}...")
        self.run_in_thread(lambda: self._apk_job(package, serial), self._apk_done)

    def _apk_job(self, package: str, serial: str):
        from eis.modules.android.backup import backup_apk

        return backup_apk(package, serial)

    def _apk_done(self, result) -> None:
        if result.get("ok"):
            self.info("APK saved", f"{result['package']}\n{result['file']}\n{result['size']}")
            self.status("APK pulled.")
        else:
            self.error("APK backup", result.get("error", "Failed."))

    # -- logcat ---------------------------------------------------------------------
    def _build_logcat_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Logcat ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.log_level_var = tk.StringVar(value="I")
        ttk.Label(bar, text="Min level:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.log_level_var, width=4, state="readonly",
                     values=("V", "D", "I", "W", "E", "F")).pack(side="left", padx=4)
        self.log_search_var = tk.StringVar()
        ttk.Label(bar, text="Filter:").pack(side="left")
        ttk.Entry(bar, textvariable=self.log_search_var, width=22).pack(side="left", padx=4)
        bar.add_button("Start", self._logcat_start, style="Accent.TButton")
        bar.add_button("Pause", self._logcat_pause)
        bar.add_button("Clear view", self._logcat_clear)
        bar.add_button("Clear device log", self._logcat_clear_device)
        bar.add_button("Export", self._logcat_export)
        self.log_counts = ttk.Label(bar, text="", style="Dim.TLabel")
        self.log_counts.pack(side="right")

        cols = ("time", "level", "tag", "message")
        self.log_tree = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        for col, text, width in (
            ("time", "Time", 130), ("level", "Lvl", 40), ("tag", "Tag", 160), ("message", "Message", 620),
        ):
            self.log_tree.heading(col, text=text)
            self.log_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=vsb.set)
        self.log_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        vsb.grid(row=1, column=1, sticky="ns")
        self.log_buffer = None
        self._log_job: str | None = None

    def _logcat_start(self) -> None:
        serial = self.serial_var.get()
        if self.log_buffer is None:
            from eis.modules.android.logcat import LogcatBuffer

            self.log_buffer = LogcatBuffer(max_lines=3000)
        if not self.log_buffer.start(serial=serial, min_level=self.log_level_var.get()):
            self.error("Logcat", "ADB not found - set the path in Settings first.")
            return
        self.status("Logcat streaming (2s UI refresh).")
        self._logcat_tick()

    def _logcat_tick(self) -> None:
        if self.log_buffer is None:
            return
        entries = self.log_buffer.query(
            search=self.log_search_var.get(), min_level=self.log_level_var.get(), limit=400
        )
        self.log_tree.delete(*self.log_tree.get_children())
        for e in entries[-300:]:
            self.log_tree.insert("", "end", values=(e.get("time", ""), e.get("level", ""),
                                                    e.get("tag", ""), e.get("message", "")[:160]))
        counts = self.log_buffer.counts_by_level()
        self.log_counts.configure(
            text=f"W:{counts.get('W', 0)}  E:{counts.get('E', 0)}  F:{counts.get('F', 0)}"
        )
        if self.log_buffer.running:
            self._log_job = self.after(2000, self._logcat_tick)

    def _logcat_pause(self) -> None:
        if self.log_buffer:
            self.log_buffer.paused = not self.log_buffer.paused
            self.status("Logcat paused." if self.log_buffer.paused else "Logcat resumed.")

    def _logcat_clear(self) -> None:
        if self.log_buffer:
            self.log_buffer.clear_screen_only()
            self.log_tree.delete(*self.log_tree.get_children())

    def _logcat_clear_device(self) -> None:
        serial = self.serial_var.get()
        if self.log_buffer and self.confirm("Clear device log", "Clear the device-side logcat buffer?"):
            result = self.log_buffer.clear_device(serial)
            self.status("Device log cleared." if result.get("ok") else result.get("error", "Failed."))

    def _logcat_export(self) -> None:
        if not self.log_buffer:
            self.info("Export", "Start logcat first.")
            return
        entries = self.log_buffer.query(min_level="V", limit=5000)
        from eis.modules.android.logcat import export_log

        path = export_log(entries, fmt="txt")
        self.info("Exported", f"Saved to:\n{path}")
