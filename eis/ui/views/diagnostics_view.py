"""Diagnostics section: OS details, installed apps, startup, processes, events, reports."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.core.utils import format_bytes, safe_filename
from eis.ui.widgets import Card, KVTable, OutputConsole, Section, ToolBar


class DiagnosticsView(Section):
    label = "Diagnostics"
    icon = "\U0001F50D"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        self._build_processes_tab(notebook)
        self._build_apps_tab(notebook)
        self._build_startup_tab(notebook)
        self._build_events_tab(notebook)
        self._build_reports_tab(notebook)

    # -- processes -----------------------------------------------------------
    def _build_processes_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Processes ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_entry("search", width=24, default="")
        bar.add_button("Search", lambda: self._load_processes())
        bar.add_button("Details", self._process_details)
        bar.add_button("End task", self._end_process, style="Danger.TButton", name="endproc")

        cols = ("pid", "name", "cpu", "ram", "user")
        self.proc_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, text, width in (
            ("pid", "PID", 70), ("name", "Name", 240), ("cpu", "CPU %", 70),
            ("ram", "RAM", 110), ("user", "User", 130),
        ):
            self.proc_tree.heading(col, text=text)
            self.proc_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=vsb.set)
        self.proc_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.proc_tree.bind("<Double-1>", lambda _e: self._process_details())

    def _load_processes(self, search: str = "") -> None:
        term = search or self._proc_search()
        self.status("Listing processes...")
        self.run_in_thread(lambda: self._proc_job(term), self._proc_done)

    def _proc_search(self) -> str:
        try:
            return self.proc_tree.master.grid_slaves(row=0)[0].get("search")  # type: ignore[attr-defined]
        except Exception:
            return ""

    def _proc_job(self, term: str):
        from eis.modules.windows.processes import list_processes

        return list_processes(search=term, limit=400)

    def _proc_done(self, rows) -> None:
        self.proc_tree.delete(*self.proc_tree.get_children())
        for p in rows:
            self.proc_tree.insert("", "end", values=(
                p["pid"], p["name"], f"{p.get('cpu_percent') or 0:.1f}",
                format_bytes(p.get("ram_bytes") or 0), p.get("user") or "-",
            ))
        self.status(f"{len(rows)} processes listed.")

    def _selected_pid(self) -> int | None:
        sel = self.proc_tree.selection()
        if not sel:
            return None
        values = self.proc_tree.item(sel[0], "values")
        try:
            return int(values[0])
        except (ValueError, IndexError):
            return None

    def _process_details(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            self.info("Details", "Select a process first.")
            return
        self.run_in_thread(lambda: self._details_job(pid), self._details_done)

    def _details_job(self, pid: int):
        from eis.modules.windows.processes import process_details

        return process_details(pid)

    def _details_done(self, details) -> None:
        if not details.get("ok"):
            self.error("Process details", details.get("error", "Unknown error."))
            return
        lines = [
            f"PID         : {details['pid']}",
            f"Name        : {details.get('name', '')}",
            f"Executable  : {details.get('exe', 'n/a')}",
            f"Command line: {details.get('cmdline', '')[:200]}",
            f"Working dir : {details.get('cwd', 'n/a')}",
            f"User        : {details.get('user', '')}",
            f"Status      : {details.get('status', '')}",
            f"Threads     : {details.get('threads', '?')}",
            f"RAM (RSS)   : {format_bytes(details.get('ram_rss', 0))}",
            f"RAM (VMS)   : {format_bytes(details.get('ram_vms', 0))}",
        ]
        self.info(f"Process {details['pid']}", "\n".join(lines))

    def _end_process(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            self.info("End task", "Select a process first.")
            return
        name = self.proc_tree.item(self.proc_tree.selection()[0], "values")[1]
        if not self.confirm(
            "End process",
            f"End process {name} (PID {pid})?\n\nUnsaved work in this program will be lost.",
        ):
            return
        from eis.modules.windows.processes import end_process

        result = end_process(pid, confirm_executed=True)
        if result.get("ok"):
            self.status(f"Process {name} ended.")
            self._load_processes()
        else:
            self.error("End task", result.get("error", "Failed."))

    # -- installed apps --------------------------------------------------------
    def _build_apps_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Installed apps ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_entry("app_search", width=30)
        bar.add_button("Search", self._search_apps)
        bar.add_button("Load all", lambda: self._load_apps(""))
        bar.add_button("Uninstall (runs app's own uninstaller)", self._uninstall_app, style="Accent.TButton")

        cols = ("name", "version", "publisher", "size")
        self.apps_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for col, text, width in (
            ("name", "Application", 320), ("version", "Version", 130),
            ("publisher", "Publisher", 220), ("size", "Est. size", 100),
        ):
            self.apps_tree.heading(col, text=text)
            self.apps_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.apps_tree.yview)
        self.apps_tree.configure(yscrollcommand=vsb.set)
        self.apps_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self._apps_cache: list[dict] = []

    def _search_apps(self) -> None:
        self._load_apps(self.apps_tree.master.grid_slaves(row=0)[0].get("app_search"))  # type: ignore[attr-defined]

    def _load_apps(self, term: str) -> None:
        self.status("Reading installed applications (10-20s first time)...")
        self.run_in_thread(lambda: self._apps_job(term), self._apps_done)

    def _apps_job(self, term: str):
        from eis.modules.windows.apps import list_installed, search_installed

        apps = list_installed()
        return search_installed(term, apps)

    def _apps_done(self, apps) -> None:
        self._apps_cache = apps
        self.apps_tree.delete(*self.apps_tree.get_children())
        for app in apps:
            self.apps_tree.insert("", "end", values=(
                app.get("name", ""), app.get("version", ""),
                app.get("publisher", ""),
                f"{app['estimated_size_mb']} MB" if app.get("estimated_size_mb") else "-",
            ))
        self.status(f"{len(apps)} applications listed.")

    def _uninstall_app(self) -> None:
        sel = self.apps_tree.selection()
        if not sel:
            self.info("Uninstall", "Select an application first.")
            return
        app_name = self.apps_tree.item(sel[0], "values")[0]
        app = next((a for a in self._apps_cache if a["name"] == app_name), None)
        if not app or not app.get("uninstall_string"):
            self.error("Uninstall", "No uninstall command found for this entry.")
            return
        if not self.confirm(
            "Run uninstaller",
            f"Launch the official uninstaller for:\n\n{app_name}\n\n{app['uninstall_string']}\n\n"
            "E.I.S. only starts the program's own uninstaller - review its dialogs.",
        ):
            return
        import os as _os
        import subprocess

        try:
            subprocess.Popen(app["uninstall_string"], shell=True)  # noqa: S602 - user-confirmed
            self.status(f"Uninstaller launched for {app_name}.")
        except OSError as exc:
            self.error("Uninstall failed", str(exc))

    # -- startup -----------------------------------------------------------------
    def _build_startup_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Startup ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Refresh", self._load_startup)
        bar.add_button("Open Windows Startup settings", lambda: self._open_startup_settings())

        cols = ("name", "command", "location")
        self.startup_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for col, text, width in (
            ("name", "Entry", 200), ("command", "Command", 420), ("location", "Location", 260),
        ):
            self.startup_tree.heading(col, text=text)
            self.startup_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.startup_tree.yview)
        self.startup_tree.configure(yscrollcommand=vsb.set)
        self.startup_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

    def _load_startup(self) -> None:
        self.status("Reading startup entries...")
        self.run_in_thread(self._startup_job, self._startup_done)

    def _startup_job(self):
        from eis.modules.windows.startup import list_startup

        return list_startup()

    def _startup_done(self, entries) -> None:
        self.startup_tree.delete(*self.startup_tree.get_children())
        for e in entries:
            self.startup_tree.insert("", "end", values=(e.get("name", ""), e.get("command", ""), e.get("location", "")))
        self.status(f"{len(entries)} startup entries.")

    def _open_startup_settings(self) -> None:
        from eis.modules.windows.startup import open_startup_settings

        result = open_startup_settings()
        if not result.get("ok"):
            self.error("Startup", result.get("error", "Windows-only."))

    # -- event log ------------------------------------------------------------------
    def _build_events_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Event log ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.level_var = tk.StringVar(value="error")
        ttk.Label(bar, text="Level:").pack(side="left")
        for level in ("critical", "error", "warning", "all"):
            ttk.Radiobutton(bar, text=level.capitalize(), value=level, variable=self.level_var).pack(side="left")
        self.log_var = tk.StringVar(value="System")
        ttk.Label(bar, text="  Log:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.log_var, values=("System", "Application", "Setup"),
                     width=12, state="readonly").pack(side="left", padx=(0, 6))
        bar.add_button("Query", self._query_events)

        self.events_summary = ttk.Label(tab, text="", style="Dim.TLabel")
        self.events_summary.grid(row=1, column=0, sticky="w", pady=(4, 0))

        cols = ("time", "level", "source", "id", "message")
        self.events_tree = ttk.Treeview(tab, columns=cols, show="headings", height=14)
        for col, text, width in (
            ("time", "Time", 150), ("level", "Level", 80), ("source", "Source", 160),
            ("id", "Event ID", 70), ("message", "Message", 480),
        ):
            self.events_tree.heading(col, text=text)
            self.events_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=vsb.set)
        self.events_tree.grid(row=2, column=0, sticky="nsew")
        vsb.grid(row=2, column=1, sticky="ns")

    def _query_events(self) -> None:
        level = self.level_var.get()
        log_name = self.log_var.get()
        self.status(f"Querying {log_name} log ({level})...")
        self.run_in_thread(lambda: self._events_job(level, log_name), self._events_done)

    def _events_job(self, level: str, log_name: str):
        from eis.modules.windows.events import event_summary, query_events

        return {"events": query_events(log_name=log_name, level=level, max_events=100),
                "summary": event_summary(days=3)}

    def _events_done(self, data) -> None:
        result = data["events"]
        self.events_tree.delete(*self.events_tree.get_children())
        if not result.get("ok"):
            self.status(f"Event query failed: {result.get('error', 'unknown')}")
            return
        for e in result.get("events", []):
            self.events_tree.insert("", "end", values=(
                e.get("time", ""), e.get("level", ""), e.get("source", ""),
                e.get("event_id", ""), e.get("message", "")[:180],
            ))
        summary = data["summary"]["logs"]
        parts = [f"{log}: {c['critical']} critical, {c['error']} errors, {c['warning']} warnings (3d)"
                 for log, c in summary.items()]
        self.events_summary.configure(text="  |  ".join(parts))
        self.status(f"{result.get('count', 0)} events shown.")

    # -- reports ------------------------------------------------------------------
    def _build_reports_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Diagnostic report ")

        card = Card(tab, "Generate a technical report")
        card.pack(fill="both", expand=True)
        ttk.Label(
            card, text="Collects system, Windows and network snapshots into a shareable file.\n"
                       "HTML is print-friendly; JSON is machine-readable; TXT is plain text.",
            style="Dim.TLabel", justify="left",
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(card)
        row.pack(anchor="w")
        self.report_fmt = tk.StringVar(value="html")
        for fmt in ("html", "txt", "json"):
            ttk.Radiobutton(row, text=fmt.upper(), value=fmt, variable=self.report_fmt).pack(side="left")
        ttk.Button(row, text="Generate report", command=self._gen_report, style="Accent.TButton").pack(side="left", padx=10)

        self.report_output = OutputConsole(card, height=8, save_name="report_result.txt")
        self.report_output.pack(fill="both", expand=True, pady=(8, 0))

    def _gen_report(self) -> None:
        fmt = self.report_fmt.get()
        self.status(f"Generating {fmt.upper()} report...")
        self.run_in_thread(lambda: self._report_job(fmt), self._report_done)

    def _report_job(self, fmt: str):
        from eis.modules.reports.generator import generate_report

        return generate_report(fmt=fmt)

    def _report_done(self, result) -> None:
        if result.get("ok"):
            import os

            self.report_output.set_text(f"Report written to:\n{result['path']}\n({result['size']} bytes)")
            self.status(f"Report generated: {safe_filename(result['path'])}")
            try:
                os.startfile(result["path"])  # noqa: S606 - opens the report for review
            except OSError:
                pass
        else:
            self.report_output.set_text(f"Failed: {result.get('error')}")
            self.error("Report", result.get("error", "Generation failed."))
