"""Repair section: SFC/DISM centers, temp cleaner, DNS flush, network reset, services."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.core.utils import format_bytes
from eis.ui.widgets import Card, OutputConsole, Section, ToolBar


class RepairView(Section):
    label = "Repair"
    icon = "\U0001F527"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._build_sfc_dism_tab(notebook)
        self._build_cleanup_tab(notebook)
        self._build_network_repair_tab(notebook)
        self._build_services_tab(notebook)
        self._build_security_tab(notebook)

    # -- SFC / DISM ------------------------------------------------------------
    def _build_sfc_dism_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" System file repair ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="SFC:").pack(side="left")
        bar.add_button("Scan now", lambda: self._run_sfc("scan"))
        bar.add_button("Verify only", lambda: self._run_sfc("verify"))
        ttk.Label(bar, text="   DISM:").pack(side="left")
        bar.add_button("CheckHealth", lambda: self._run_dism("checkhealth"))
        bar.add_button("ScanHealth", lambda: self._run_dism("scanhealth"))
        bar.add_button("RestoreHealth", lambda: self._run_dism("restorehealth"), style="Accent.TButton")

        ttk.Label(
            tab, text="Repairs run elevated (UAC prompt appears) and take several minutes.\n"
                     "Output is saved under data/logs/sfc_dism/.",
            style="Dim.TLabel", justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(26, 4))

        self.repair_console = OutputConsole(tab, height=18, save_name="repair_output.txt")
        self.repair_console.grid(row=1, column=0, sticky="nsew")

    def _run_sfc(self, operation: str) -> None:
        if not self.confirm("SFC", f"Run SFC {operation.upper()}?\n\nAn elevation prompt will appear."):
            return
        self.status(f"Running SFC {operation} (this can take 5-20 minutes)...")
        self.run_in_thread(lambda: self._sfc_job(operation), self._repair_done)

    def _sfc_job(self, operation: str):
        from eis.modules.windows.repair import run_sfc

        return run_sfc(operation)

    def _run_dism(self, operation: str) -> None:
        if not self.confirm("DISM", f"Run DISM {operation}?\n\nAn elevation prompt will appear."):
            return
        self.status(f"Running DISM {operation} (this can take 10-40 minutes)...")
        self.run_in_thread(lambda: self._dism_job(operation), self._repair_done)

    def _dism_job(self, operation: str):
        from eis.modules.windows.repair import run_dism

        return run_dism(operation)

    def _repair_done(self, result) -> None:
        lines = [f"Command : {result.get('command', '?')}"]
        if result.get("elevated"):
            lines.append("Mode    : elevated (output below is captured from the elevated run)")
        if result.get("integrity_violations"):
            lines.append(f"Verdict : {result['integrity_violations']}")
        if result.get("log_file"):
            lines.append(f"Log     : {result['log_file']}")
        lines.append("")
        lines.append(result.get("output") or result.get("error") or "(no output)")
        self.repair_console.set_text("\n".join(lines))
        self.status("Repair operation finished." if result.get("ok") else "Repair operation reported a problem.")

    # -- cleanup ---------------------------------------------------------------
    def _build_cleanup_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Cleanup ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Estimate", self._estimate_cleanup)
        bar.add_button("Flush DNS cache", self._flush_dns)
        bar.add_button("Clean selected", self._clean_selected, style="Danger.TButton", name="clean")

        ttk.Label(tab, text="Select locations, then Estimate. Cleaning removes files older than 24h only.",
                  style="Dim.TLabel").grid(row=0, column=0, sticky="ew", pady=(26, 4))

        self.clean_vars: dict[str, tk.BooleanVar] = {}
        self._cleanup_list_frame = ttk.Frame(tab)
        self._cleanup_list_frame.grid(row=1, column=0, sticky="new")
        self._cleanup_targets: list[dict] = []

        self.clean_console = OutputConsole(tab, height=10, save_name="cleanup_result.txt")
        self.clean_console.grid(row=2, column=0, sticky="nsew", pady=(8, 0))

    def _estimate_cleanup(self) -> None:
        self.status("Measuring cleanup locations...")
        self.run_in_thread(self._targets_job, self._targets_done)

    def _targets_job(self):
        from eis.modules.windows.maintenance import cleaner_targets

        return cleaner_targets()

    def _targets_done(self, targets) -> None:
        self._cleanup_targets = targets
        frame = self._cleanup_list_frame
        for w in frame.winfo_children():
            w.destroy()
        self.clean_vars.clear()
        for t in targets:
            var = tk.BooleanVar(value=bool(t.get("size_bytes")))
            row = ttk.Frame(frame)
            row.pack(fill="x", anchor="w")
            cb = ttk.Checkbutton(row, text=f"{t['name']}  -  {format_bytes(t.get('size_bytes', 0))}",
                                 variable=var)
            cb.pack(side="left")
            if not t.get("allowed"):
                ttk.Label(row, text="(skipped: protected)", style="Dim.TLabel").pack(side="left", padx=8)
            self.clean_vars[t["name"]] = var
        total = sum(t.get("size_bytes", 0) for t in targets if t.get("allowed"))
        self.status(f"Estimated recoverable: {format_bytes(total)}.")

    def _clean_selected(self) -> None:
        selected = [name for name, var in self.clean_vars.items() if var.get()]
        if not selected:
            self.info("Cleanup", "Select at least one location.")
            return
        if not self.confirm(
            "Delete temporary files",
            "Delete temp files in:\n\n  " + "\n  ".join(selected) +
            "\n\nOnly files older than 24 hours are removed. Continue?",
        ):
            return
        self.status("Cleaning...")
        self.run_in_thread(lambda: self._clean_job(selected), self._clean_done)

    def _clean_job(self, selected):
        from eis.modules.windows.maintenance import clean

        return clean(selected, confirm_executed=True)

    def _clean_done(self, result) -> None:
        lines = [f"Cleaned: {result.get('cleaned_human', '?')}", ""]
        for loc in result.get("locations", []):
            lines.append(f"- {loc['name']}")
            if loc.get("errors"):
                lines.append(f"    ({len(loc['errors'])} items skipped - in use)")
        if result.get("errors"):
            lines.append("\nSkipped: " + "; ".join(result["errors"][:5]))
        self.clean_console.set_text("\n".join(lines))
        self.status("Cleanup finished.")
        self._estimate_cleanup()

    def _flush_dns(self) -> None:
        self.status("Flushing DNS cache (elevation may be requested)...")
        self.run_in_thread(self._flush_job, self._flush_done)

    def _flush_job(self):
        from eis.modules.windows.maintenance import flush_dns

        return flush_dns()

    def _flush_done(self, result) -> None:
        self.clean_console.set_text(result.get("output") or result.get("error") or "Done.")
        self.status("DNS cache flushed." if result.get("ok") else "Flush failed.")

    # -- network repair ----------------------------------------------------------
    def _build_network_repair_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Network reset ")

        card = Card(tab, "Windows network reset (advanced)")
        card.pack(fill="both", expand=True)
        ttk.Label(
            card,
            text="Each step fixes different classes of network failure. Read before selecting:\n\n"
                 "  - Winsock reset  : fixes corrupted network layers after malware/tool misuse\n"
                 "  - TCP/IP reset   : restores default IP config (static IPs are lost)\n"
                 "  - Firewall reset : restores default rules (custom rules are lost)\n"
                 "  - DNS flush      : clears resolver cache (harmless)\n"
                 "  - Release/renew  : requests a new DHCP lease (brief disconnect)\n\n"
                 "A restart is required after Winsock/TCP-IP resets.",
            justify="left", style="Dim.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        self.reset_vars: dict[str, tk.BooleanVar] = {}
        for sid, label in (
            ("dns", "Flush DNS cache (safe)"),
            ("release_renew", "Release & renew DHCP lease"),
            ("winsock", "Reset Winsock catalog"),
            ("tcp_ip", "Reset TCP/IP stack"),
            ("firewall", "Reset firewall to defaults"),
        ):
            var = tk.BooleanVar(value=False)
            self.reset_vars[sid] = var
            ttk.Checkbutton(card, text=label, variable=var).pack(anchor="w")

        ttk.Button(card, text="Run selected steps", command=self._run_reset, style="Danger.TButton").pack(anchor="w", pady=(10, 0))
        self.reset_console = OutputConsole(card, height=8, save_name="network_reset.txt")
        self.reset_console.pack(fill="both", expand=True, pady=(8, 0))

    def _run_reset(self) -> None:
        steps = [sid for sid, var in self.reset_vars.items() if var.get()]
        if not steps:
            self.info("Network reset", "Select at least one step.")
            return
        if not self.confirm(
            "Network reset",
            "Selected steps will run (elevated). Connectivity may drop briefly;\n"
            "Winsock/TCP-IP resets require a restart. Continue?",
        ):
            return
        self.status("Running network reset steps...")
        self.run_in_thread(lambda: self._reset_job(steps), self._reset_done)

    def _reset_job(self, steps):
        from eis.modules.windows.maintenance import perform_network_reset

        return perform_network_reset(steps, confirm_executed=True)

    def _reset_done(self, result) -> None:
        lines = []
        for step in result.get("steps", []):
            mark = "OK " if step.get("ok") else "ERR"
            lines.append(f"[{mark}] {step['command']}\n      {step.get('output') or step.get('error', '')}")
        if not lines:
            lines.append(result.get("error", "Nothing ran."))
        self.reset_console.set_text("\n".join(lines))
        self.status("Network reset finished - a restart completes Winsock/TCP-IP resets.")

    # -- services ---------------------------------------------------------------
    def _build_services_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Services ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_entry("svc_search", width=24)
        bar.add_button("Search", self._load_services)
        bar.add_button("Start", lambda: self._svc_action("start"))
        bar.add_button("Stop", lambda: self._svc_action("stop"))
        bar.add_button("Restart", lambda: self._svc_action("restart"))
        bar.add_button("Open services.msc", lambda: self._open_services_console())

        cols = ("name", "status", "startup", "desc")
        self.svc_tree = ttk.Treeview(tab, columns=cols, show="headings", height=17)
        for col, text, width in (
            ("name", "Service", 200), ("status", "Status", 90),
            ("startup", "Startup", 90), ("desc", "Description", 500),
        ):
            self.svc_tree.heading(col, text=text)
            self.svc_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.svc_tree.yview)
        self.svc_tree.configure(yscrollcommand=vsb.set)
        self.svc_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self._svc_rows: list[dict] = []

    def _load_services(self) -> None:
        term = self.svc_tree.master.grid_slaves(row=0)[0].get("svc_search")  # type: ignore[attr-defined]
        self.status("Listing services...")
        self.run_in_thread(lambda: self._svc_job(term), self._svc_done)

    def _svc_job(self, term: str):
        from eis.modules.windows.services import list_services

        return list_services(search=term, limit=400)

    def _svc_done(self, rows) -> None:
        self._svc_rows = rows
        self.svc_tree.delete(*self.svc_tree.get_children())
        for s in rows:
            self.svc_tree.insert("", "end", values=(
                s.get("name", ""), s.get("status", ""), s.get("startup_type", ""),
                (s.get("display_name", "") + " - " + s.get("description", ""))[:150],
            ))
        self.status(f"{len(rows)} services.")

    def _svc_action(self, action: str) -> None:
        sel = self.svc_tree.selection()
        if not sel:
            self.info("Services", "Select a service first.")
            return
        name = self.svc_tree.item(sel[0], "values")[0]
        if not self.confirm("Service action", f"{action.capitalize()} service '{name}'?"):
            return
        self.run_in_thread(lambda: self._svc_action_job(name, action), self._svc_action_done)

    def _svc_action_job(self, name: str, action: str):
        from eis.modules.windows.services import change_service_state

        return change_service_state(name, action, confirm_executed=True)

    def _svc_action_done(self, result) -> None:
        if result.get("ok"):
            self.status(f"Service {result['service']}: {result['action']} done.")
            self._load_services()
        else:
            self.error("Service action", result.get("error", "Failed (try running as admin)."))

    def _open_services_console(self) -> None:
        from eis.modules.windows.services import open_services_console

        open_services_console()

    # -- security -----------------------------------------------------------------
    def _build_security_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Security & restore ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Firewall status", self._firewall_status)
        bar.add_button("Open firewall console", lambda: self._open_wf())
        bar.add_button("Defender status", self._defender_status)
        bar.add_button("Quick scan", lambda: self._defender_scan("quick"))
        bar.add_button("Restore points", self._list_restore_points)
        bar.add_button("Create restore point", self._create_restore_point, style="Accent.TButton")

        self.security_console = OutputConsole(tab, height=20, save_name="security_status.txt")
        self.security_console.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def _firewall_status(self) -> None:
        self.run_in_thread(self._fw_job, self._fw_done)

    def _fw_job(self):
        from eis.modules.windows.security import firewall_status

        return firewall_status()

    def _fw_done(self, result) -> None:
        lines = ["Windows Firewall profiles:"]
        for name, prof in result.get("profiles", {}).items():
            state = "ON" if prof.get("enabled") else "OFF"
            lines.append(f"  {name.capitalize():<8} {state}   inbound={prof.get('inbound')} outbound={prof.get('outbound')}")
        if result.get("active_profile"):
            lines.append(f"Active profile: {result['active_profile']}")
        self.security_console.set_text("\n".join(lines))
        self.status("Firewall status loaded.")

    def _open_wf(self) -> None:
        from eis.modules.windows.security import open_firewall_console

        open_firewall_console()

    def _defender_status(self) -> None:
        self.run_in_thread(self._def_job, self._def_done)

    def _def_job(self):
        from eis.modules.windows.security import defender_status

        return defender_status()

    def _def_done(self, result) -> None:
        s = result.get("status", {})
        lines = [
            "Windows Defender status (inspection only - E.I.S. never disables protection):",
            f"  Antivirus        : {'ON' if s.get('antivirus_enabled') else 'OFF'}",
            f"  Real-time        : {'ON' if s.get('real_time_enabled') else 'OFF'}",
            f"  Behavior monitor : {'ON' if s.get('behavior_monitor') else 'OFF'}",
            f"  Tamper protection: {'ON' if s.get('tamper_protected') else 'OFF'}",
            f"  Signatures       : {s.get('signature_updated') or 'n/a'}",
        ]
        threats = result.get("threats", [])
        if threats:
            lines.append(f"  Recent detections: {len(threats)}")
            for t in threats[:5]:
                lines.append(f"    - {t.get('time', '')} {t.get('process', '')}")
        else:
            lines.append("  Recent detections: none recorded")
        self.security_console.set_text("\n".join(lines))
        self.status("Defender status loaded.")

    def _defender_scan(self, scan_type: str) -> None:
        if not self.confirm("Defender scan", f"Start a {scan_type} scan? It runs in the background."):
            return
        self.run_in_thread(lambda: self._scan_start_job(scan_type), self._scan_start_done)

    def _scan_start_job(self, scan_type: str):
        from eis.modules.windows.security import start_defender_scan

        return start_defender_scan(scan_type, confirm_executed=True)

    def _scan_start_done(self, result) -> None:
        self.security_console.append(result.get("note") if result.get("ok") else result.get("error", "Failed."))
        self.status("Scan started.")

    def _list_restore_points(self) -> None:
        self.run_in_thread(self._rp_job, self._rp_done)

    def _rp_job(self):
        from eis.modules.windows.security import restore_point_status

        return restore_point_status()

    def _rp_done(self, result) -> None:
        points = result.get("points", [])
        lines = [f"Restore points found: {len(points)}"]
        for p in points[:10]:
            lines.append(f"  #{p.get('seq')}  {p.get('time', '')}  {p.get('description', '')}")
        if not points:
            lines.append("  (none - consider creating one before repairs)")
        self.security_console.set_text("\n".join(lines))
        self.status("Restore points listed.")

    def _create_restore_point(self) -> None:
        if not self.confirm(
            "Create restore point",
            "Create a system restore point now?\n\nElevation may be requested. Windows limits this to once per 24h.",
        ):
            return
        self.status("Creating restore point...")
        self.run_in_thread(self._rp_create_job, self._rp_create_done)

    def _rp_create_job(self):
        from eis.modules.windows.security import create_restore_point

        return create_restore_point("E.I.S. Core checkpoint", confirm_executed=True)

    def _rp_create_done(self, result) -> None:
        if result.get("ok"):
            self.security_console.append("Restore point created.")
            self.status("Restore point created.")
        else:
            self.security_console.append(f"Restore point failed: {result.get('error') or result.get('output', '')}")
            self.status("Restore point failed.")
