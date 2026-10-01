"""System section: information, hardware scan, RAM/CPU monitors, storage."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.core.utils import format_bytes, format_duration, format_percent
from eis.ui.theme import palette
from eis.ui.widgets import Card, KVTable, OutputConsole, Section, ToolBar


class SystemView(Section):
    label = "System"
    icon = "\U0001F5A5"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        bar = ToolBar(self)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Refresh (F5)", self.refresh, name="refresh")
        bar.add_button("Scan hardware", self._scan_hardware, name="scan")
        bar.add_button("Check disk health", self._check_health, name="health")

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._build_info_tab(notebook)
        self._build_monitor_tab(notebook)
        self._build_storage_tab(notebook)

    # ------------------------------------------------------------------
    def _build_info_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" System information ")

        self.info_table = KVTable(tab, height=16)
        self.info_table.grid(row=0, column=0, sticky="nsew")

    def _build_monitor_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        parent.add(tab, text=" Live monitors ")

        cpu_card = Card(tab, "CPU")
        cpu_card.grid(row=0, column=0, sticky="new", padx=(0, 4))
        self.cpu_bar = ttk.Progressbar(cpu_card, maximum=100, length=200)
        self.cpu_bar.pack(fill="x", pady=(2, 4))
        self.cpu_label = ttk.Label(cpu_card, text="CPU: -")
        self.cpu_label.pack(anchor="w")
        self.cpu_detail = ttk.Label(cpu_card, text="", style="Dim.TLabel", wraplength=380, justify="left")
        self.cpu_detail.pack(anchor="w", pady=(2, 0))

        ram_card = Card(tab, "Memory")
        ram_card.grid(row=0, column=1, sticky="new", padx=(4, 0))
        self.ram_bar = ttk.Progressbar(ram_card, maximum=100, length=200)
        self.ram_bar.pack(fill="x", pady=(2, 4))
        self.ram_label = ttk.Label(ram_card, text="RAM: -")
        self.ram_label.pack(anchor="w")
        self.swap_label = ttk.Label(ram_card, text="", style="Dim.TLabel")
        self.swap_label.pack(anchor="w", pady=(2, 0))

        auto = ttk.Frame(tab)
        auto.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto, text="Auto-refresh every 2s", variable=self.auto_var,
                        command=self._toggle_auto).pack(side="left")
        self._auto_job: str | None = None

    def _build_storage_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Storage ")

        self.drive_table = KVTable(tab, columns=("Drive", "Filesystem / capacity"), height=8)
        self.drive_table.grid(row=0, column=0, sticky="nsew")

        self.health_console = OutputConsole(tab, height=8, save_name="disk_health.txt")
        self.health_console.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.status("Collecting system information...")
        self.run_in_thread(self._collect_info, self._show_info)

    def _collect_info(self):
        from eis.modules.system.system_info import collect

        return collect()

    def _show_info(self, info) -> None:
        rows = [
            ("Hostname", info.get("hostname", "?")),
            ("Operating system", f"{info.get('os_edition', '?')} {info.get('os_build', '')}"),
            ("Platform", info.get("platform", "?")),
            ("Architecture", info.get("architecture", "?")),
            ("CPU", info.get("cpu_name", info.get("processor", "?"))),
            ("Cores / threads", f"{info.get('cpu_cores', '?')} / {info.get('cpu_threads', '?')}"),
            ("Motherboard", f"{info.get('motherboard', '?')} (SN: {info.get('motherboard_serial', 'n/a')})"),
            ("BIOS", f"{info.get('bios_vendor', '?')} {info.get('bios_version', '')} ({info.get('bios_release', 'n/a')})"),
            ("GPU(s)", "; ".join(info.get("gpus", [])) or "n/a"),
            ("RAM total", f"{info.get('ram_total_gb', '?')} GB"),
            ("Uptime", format_duration(info.get("uptime_seconds", 0))),
            ("Running as admin", str(info.get("is_admin", False))),
            ("Python", info.get("python_version", "?")),
        ]
        self.info_table.set_rows(rows)
        self.status("System information updated.")

    # ------------------------------------------------------------------
    def _scan_hardware(self) -> None:
        self.status("Scanning hardware (10-30s)...")
        self.run_in_thread(self._scan_job, self._scan_done)

    def _scan_job(self):
        from eis.modules.system.hardware import scan

        return scan()

    def _scan_done(self, result) -> None:
        rows: list[tuple[str, str]] = []
        categories = result.get("categories", {})
        for cat, items in categories.items():
            for i, item in enumerate(items, start=1):
                name = str(item.get("name") or item.get("product") or item.get("slot") or f"# {i}")
                detail = ", ".join(f"{k}={v}" for k, v in item.items()
                                   if k not in ("name", "product") and v)
                rows.append((f"{cat} #{i}: {name}", detail[:160]))
        for problem in result.get("problem_devices", []):
            rows.append((f"PROBLEM: {problem.get('name', '?')}",
                         f"class={problem.get('class', '?')} status={problem.get('status', '?')}"))
        self.info_table.set_rows(rows)
        self.status(f"Hardware scan complete: {sum(len(v) for v in categories.values())} devices.")

    def _check_health(self) -> None:
        self.status("Querying disk health (SMART)...")
        self.run_in_thread(self._health_job, self._health_done)

    def _health_job(self):
        from eis.modules.system.storage import disk_health, health_summary

        return {"summary": health_summary(), "first": disk_health()}

    def _health_done(self, result) -> None:
        lines = []
        for disk in result["summary"].get("disks", []):
            mark = "OK" if str(disk.get("health", "")).lower() == "healthy" else "!!"
            lines.append(f"[{mark}] {disk['name']} - {disk['media']} {disk['size_gb']} GB - {disk['health']}")
        first = result.get("first", {})
        if first.get("temperature_c") is not None:
            lines.append(f"Temperature: {first['temperature_c']} C")
        if first.get("wear") is not None:
            lines.append(f"Wear level: {first['wear']}%")
        if first.get("power_on_hours") is not None:
            lines.append(f"Power-on hours: {first['power_on_hours']}")
        if not lines:
            lines.append("No storage reliability data available on this system.")
        self.health_console.set_text("\n".join(lines))
        self.status("Disk health updated.")

    # ------------------------------------------------------------------
    def _toggle_auto(self) -> None:
        if self.auto_var.get():
            self._auto_tick()
        elif self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None

    def _auto_tick(self) -> None:
        if not self.auto_var.get():
            return
        self.run_in_thread(self._monitor_job, self._monitor_done)
        self._auto_job = self.after(2000, self._auto_tick)

    def _monitor_job(self):
        from eis.modules.system.monitors import cpu_stats, ram_stats

        return {"cpu": cpu_stats(interval=0.15), "ram": ram_stats()}

    def _monitor_done(self, data) -> None:
        cpu = data["cpu"]
        ram = data["ram"]
        if cpu.get("percent_total") is not None:
            self.cpu_bar["value"] = cpu["percent_total"]
            self.cpu_label.configure(
                text=f"CPU: {format_percent(cpu['percent_total'])}"
                     + (f"  @ {cpu['freq_mhz']} MHz" if cpu.get("freq_mhz") else "")
                     + (f"  {cpu['temp_c']} C" if cpu.get("temp_c") is not None else "")
            )
            per_core = cpu.get("percent_per_core") or []
            if per_core:
                self.cpu_detail.configure(
                    text="Per core: " + " | ".join(f"{c:.0f}%" for c in per_core)
                )
        if ram.get("total"):
            self.ram_bar["value"] = ram["percent"]
            self.ram_label.configure(
                text=f"RAM: {format_percent(ram['percent'])} used - "
                     f"{format_bytes(ram['available_bytes'])} free of {format_bytes(ram['total'])}"
            )
            self.swap_label.configure(
                text=f"Swap: {format_bytes(ram.get('swap_used', 0))} / {format_bytes(ram.get('swap_total', 0))}"
                     f" ({format_percent(ram.get('swap_percent', 0))})"
            )
