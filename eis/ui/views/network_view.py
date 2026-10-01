"""Network section: adapters, ping, DNS, connectivity, Wi-Fi, ports, discovery."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.ui.widgets import Card, KVTable, OutputConsole, Section, ToolBar


class NetworkView(Section):
    label = "Network"
    icon = "\U0001F310"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._build_adapters_tab(notebook)
        self._build_ping_tab(notebook)
        self._build_dns_tab(notebook)
        self._build_connectivity_tab(notebook)
        self._build_wifi_tab(notebook)
        self._build_ports_tab(notebook)
        self._build_discovery_tab(notebook)

    # -- adapters ------------------------------------------------------------
    def _build_adapters_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Adapters ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Refresh", self._load_adapters)
        self.adapter_table = KVTable(tab, height=18)
        self.adapter_table.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

    def _load_adapters(self) -> None:
        self.status("Reading network adapters...")
        self.run_in_thread(self._adapters_job, self._adapters_done)

    def _adapters_job(self):
        from eis.modules.network.adapters import list_adapters, public_ip

        return {"adapters": list_adapters(), "public": public_ip()}

    def _adapters_done(self, data) -> None:
        rows: list[tuple[str, str]] = []
        for a in data["adapters"]:
            name = a.get("name", "?")
            rows.append((f"{name} - status", a.get("status", "?")))
            rows.append((f"{name} - adapter", a.get("description", "")))
            rows.append((f"{name} - MAC", a.get("mac", "n/a")))
            rows.append((f"{name} - link", a.get("link_speed", "")))
            ip = a.get("ip_config", {})
            if ip.get("ipv4"):
                rows.append((f"{name} - IPv4", ", ".join(ip["ipv4"])))
            if ip.get("ipv6"):
                rows.append((f"{name} - IPv6", ", ".join(ip["ipv6"])))
            if ip.get("gateway"):
                rows.append((f"{name} - gateway", ", ".join(ip["gateway"])))
            if a.get("dns_servers"):
                rows.append((f"{name} - DNS", ", ".join(a["dns_servers"])))
            rows.append(("", ""))
        if data.get("public"):
            rows.append(("Public IP", data["public"]))
        self.adapter_table.set_rows(rows)
        self.status("Network adapters updated.")

    # -- ping -------------------------------------------------------------------
    def _build_ping_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=0)
        tab.rowconfigure(1, weight=0)
        tab.rowconfigure(2, weight=1)
        parent.add(tab, text=" Ping ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.ping_host_var = tk.StringVar(value="8.8.8.8")
        ttk.Label(bar, text="Host:").pack(side="left")
        ttk.Entry(bar, textvariable=self.ping_host_var, width=28).pack(side="left", padx=4)
        self.ping_count_var = tk.StringVar(value="4")
        ttk.Label(bar, text="Count:").pack(side="left")
        ttk.Spinbox(bar, from_=1, to=50, textvariable=self.ping_count_var, width=5).pack(side="left", padx=4)
        bar.add_button("Ping", self._do_ping, style="Accent.TButton")

        self.ping_stats = ttk.Label(tab, text="", font=("Segoe UI", 11, "bold"))
        self.ping_stats.grid(row=1, column=0, sticky="w", pady=4)

        self.ping_console = OutputConsole(tab, height=16, save_name="ping_results.txt")
        self.ping_console.grid(row=2, column=0, sticky="nsew")

    def _do_ping(self) -> None:
        host = self.ping_host_var.get().strip()
        try:
            count = max(1, min(50, int(self.ping_count_var.get())))
        except ValueError:
            count = 4
        self.status(f"Pinging {host} x{count}...")
        self.run_in_thread(lambda: self._ping_job(host, count), self._ping_done)

    def _ping_job(self, host: str, count: int):
        from eis.modules.network.ping import ping_host

        return ping_host(host, count=count)

    def _ping_done(self, result) -> None:
        if result.get("ok"):
            self.ping_stats.configure(
                text=f"avg {result.get('avg_ms', '-')} ms   min {result.get('min_ms', '-')}   "
                     f"max {result.get('max_ms', '-')}   jitter {result.get('jitter_ms', '-')} ms   "
                     f"loss {result.get('loss_percent', 0)}%"
            )
        else:
            self.ping_stats.configure(text="Ping failed.")
        self.ping_console.append(result.get("output", result.get("error", "")))
        self.status("Ping complete.")

    # -- dns ----------------------------------------------------------------------
    def _build_dns_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        parent.add(tab, text=" DNS ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.dns_host_var = tk.StringVar(value="example.com")
        ttk.Label(bar, text="Host:").pack(side="left")
        ttk.Entry(bar, textvariable=self.dns_host_var, width=24).pack(side="left", padx=4)
        self.dns_type_var = tk.StringVar(value="A")
        ttk.Combobox(bar, textvariable=self.dns_type_var, width=7, state="readonly",
                     values=("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR")).pack(side="left", padx=4)
        self.dns_server_var = tk.StringVar(value="")
        ttk.Label(bar, text="Server:").pack(side="left")
        ttk.Entry(bar, textvariable=self.dns_server_var, width=14).pack(side="left", padx=4)
        bar.add_button("Resolve", self._dns_resolve)
        bar.add_button("Lookup records", self._dns_lookup, style="Accent.TButton")
        bar.add_button("Benchmark", self._dns_benchmark)

        self.dns_console = OutputConsole(tab, height=18, save_name="dns_results.txt")
        self.dns_console.grid(row=2, column=0, sticky="nsew", pady=(6, 0))

    def _dns_resolve(self) -> None:
        host = self.dns_host_var.get().strip()
        self.run_in_thread(lambda: self._resolve_job(host), self._resolve_done)

    def _resolve_job(self, host: str):
        from eis.modules.network.dns_tools import resolve_hostname

        return resolve_hostname(host)

    def _resolve_done(self, result) -> None:
        if result.get("ok"):
            lines = [f"{result['host']} resolves to:"]
            lines += [f"  IPv4: {a}" for a in result.get("ipv4", [])]
            lines += [f"  IPv6: {a}" for a in result.get("ipv6", [])]
        else:
            lines = [f"Resolution failed: {result.get('error')}"]
        self.dns_console.append("\n".join(lines))

    def _dns_lookup(self) -> None:
        host = self.dns_host_var.get().strip()
        rtype = self.dns_type_var.get()
        server = self.dns_server_var.get().strip()
        self.run_in_thread(lambda: self._lookup_job(host, rtype, server), self._lookup_done)

    def _lookup_job(self, host: str, rtype: str, server: str):
        from eis.modules.network.dns_tools import lookup_records

        return lookup_records(host, rtype, server)

    def _lookup_done(self, result) -> None:
        if result.get("ok"):
            lines = [f"{result['type']} records for {result['host']} (via {result['server']})"]
            lines += [f"  {r}" for r in result.get("records", [])]
        else:
            lines = [f"Lookup failed: {result.get('error')}"]
        self.dns_console.append("\n".join(lines))

    def _dns_benchmark(self) -> None:
        self.status("Benchmarking DNS servers...")
        self.run_in_thread(self._bench_job, self._bench_done)

    def _bench_job(self):
        from eis.modules.network.dns_tools import dns_benchmark

        return dns_benchmark()

    def _bench_done(self, result) -> None:
        lines = [f"DNS benchmark for {result['host']}:"]
        for r in result.get("results", []):
            status = f"{r['ms']} ms" if r["ok"] else "FAILED"
            lines.append(f"  {r['server']:<16} {status}")
        self.dns_console.append("\n".join(lines))
        self.status("DNS benchmark complete.")

    # -- connectivity ---------------------------------------------------------------
    def _build_connectivity_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Connectivity ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Run full test", self._run_connectivity, style="Accent.TButton")

        self.conn_verdict = ttk.Label(tab, text="Run the test to check gateway, DNS and Internet.",
                                      font=("Segoe UI", 11, "bold"))
        self.conn_verdict.grid(row=0, column=0, sticky="ew", pady=(26, 4))

        self.conn_console = OutputConsole(tab, height=16, save_name="connectivity_test.txt")
        self.conn_console.grid(row=1, column=0, sticky="nsew")

    def _run_connectivity(self) -> None:
        self.status("Testing connectivity (gateway, DNS, Internet)...")
        self.run_in_thread(self._conn_job, self._conn_done)

    def _conn_job(self):
        from eis.modules.network.connectivity import run_connectivity_test

        return run_connectivity_test()

    def _conn_done(self, result) -> None:
        self.conn_verdict.configure(text=result.get("verdict", ""))
        lines = [f"Connectivity test - {result.get('timestamp', '')}"]
        for step in result.get("steps", []):
            mark = "PASS" if step.get("ok") else "FAIL"
            target = step.get("target") or "-"
            lines.append(f"  [{mark}] {step['step']:<16} {target:<20} {step.get('detail', '')}")
        self.conn_console.set_text("\n".join(lines))
        self.status("Connectivity test complete.")

    # -- wifi -------------------------------------------------------------------------
    def _build_wifi_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Wi-Fi ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Connection info", self._wifi_info)
        bar.add_button("Nearby networks", self._wifi_scan)
        bar.add_button("Saved profiles", self._wifi_profiles)

        cols = ("ssid", "auth", "signal", "channel")
        self.wifi_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, text, width in (
            ("ssid", "SSID", 240), ("auth", "Authentication", 180),
            ("signal", "Signal", 90), ("channel", "Channel", 80),
        ):
            self.wifi_tree.heading(col, text=text)
            self.wifi_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.wifi_tree.yview)
        self.wifi_tree.configure(yscrollcommand=vsb.set)
        self.wifi_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        vsb.grid(row=1, column=1, sticky="ns")

        self.wifi_console = OutputConsole(tab, height=7, save_name="wifi_info.txt")
        self.wifi_console.grid(row=2, column=0, sticky="nsew", pady=(6, 0))

    def _wifi_info(self) -> None:
        self.run_in_thread(self._wifi_job, self._wifi_done)

    def _wifi_job(self):
        from eis.modules.network.wifi import current_connection

        return current_connection()

    def _wifi_done(self, result) -> None:
        if not result.get("ok"):
            self.wifi_console.set_text(f"Wi-Fi info unavailable: {result.get('error')}")
            return
        lines = [
            f"SSID        : {result.get('ssid', 'n/a')}",
            f"State       : {result.get('state', 'n/a')}",
            f"Adapter     : {result.get('adapter', 'n/a')}",
            f"Signal      : {result.get('signal', '')} ({result.get('signal_quality', '')})",
            f"Channel     : {result.get('channel', 'n/a')}",
            f"Radio type  : {result.get('radio_type', 'n/a')}",
            f"Band        : {result.get('band', 'n/a')}",
            f"Auth        : {result.get('authentication', 'n/a')}",
            f"RX/TX rate  : {result.get('receive_rate', '?')} / {result.get('transmit_rate', '?')} Mbps",
        ]
        self.wifi_console.set_text("\n".join(lines))
        self.status("Wi-Fi info loaded.")

    def _wifi_scan(self) -> None:
        self.status("Scanning nearby networks...")
        self.run_in_thread(self._wifi_scan_job, self._wifi_scan_done)

    def _wifi_scan_job(self):
        from eis.modules.network.wifi import nearby_networks

        return nearby_networks()

    def _wifi_scan_done(self, networks) -> None:
        self.wifi_tree.delete(*self.wifi_tree.get_children())
        for net in networks:
            for i, b in enumerate(net.get("bssids", [{}])):
                self.wifi_tree.insert("", "end", values=(
                    net.get("ssid", "") if i == 0 else "",
                    net.get("authentication", ""),
                    f"{b.get('signal_percent', '?')}%" if b.get("signal_percent") else "?",
                    b.get("channel") or "?",
                ))
        self.status(f"{len(networks)} networks in range.")

    def _wifi_profiles(self) -> None:
        self.run_in_thread(self._wifi_prof_job, self._wifi_prof_done)

    def _wifi_prof_job(self):
        from eis.modules.network.wifi import saved_networks

        return saved_networks()

    def _wifi_prof_done(self, profiles) -> None:
        names = ", ".join(p["name"] for p in profiles) or "(none)"
        self.wifi_console.set_text(f"Saved WLAN profiles ({len(profiles)}):\n  {names}")

    # -- ports -------------------------------------------------------------------------
    def _build_ports_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Port test ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.port_host_var = tk.StringVar(value="localhost")
        ttk.Label(bar, text="Host:").pack(side="left")
        ttk.Entry(bar, textvariable=self.port_host_var, width=22).pack(side="left", padx=4)
        self.port_list_var = tk.StringVar(value="80, 443, 3389")
        ttk.Label(bar, text="Ports (comma separated):").pack(side="left")
        ttk.Entry(bar, textvariable=self.port_list_var, width=22).pack(side="left", padx=4)
        bar.add_button("Test ports", self._test_ports, style="Accent.TButton")

        self.port_console = OutputConsole(tab, height=18, save_name="port_test.txt")
        self.port_console.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def _test_ports(self) -> None:
        host = self.port_host_var.get().strip()
        raw = self.port_list_var.get()
        try:
            ports = [int(p.strip()) for p in raw.split(",") if p.strip().isdigit()]
        except ValueError:
            ports = []
        if not ports:
            self.info("Port test", "Enter valid ports, e.g. 80, 443, 3389.")
            return
        self.status(f"Testing {len(ports)} ports on {host}...")
        self.run_in_thread(lambda: self._port_job(host, ports), self._port_done)

    def _port_job(self, host: str, ports):
        from eis.modules.network.ports import test_ports

        return test_ports(host, ports)

    def _port_done(self, result) -> None:
        lines = [f"Port test for {result['host']}:"]
        for r in result.get("results", []):
            if r.get("open"):
                svc = f" ({r['service']})" if r.get("service") else ""
                lines.append(f"  [OPEN]   {r['port']:<6} {r.get('ms', '?')} ms{svc}")
            else:
                reason = r.get("reason", "closed")
                lines.append(f"  [closed] {r['port']:<6} {reason}")
        self.port_console.set_text("\n".join(lines))
        self.status(f"{result.get('open_count', 0)} of {result.get('tested', 0)} ports open.")

    # -- discovery ----------------------------------------------------------------------
    def _build_discovery_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" LAN discovery ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.discovery_ports_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Probe common TCP ports (slower)", variable=self.discovery_ports_var).pack(side="left")
        bar.add_button("Discover devices", self._discover, style="Accent.TButton")

        cols = ("ip", "mac", "hostname", "vendor", "ports")
        self.lan_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for col, text, width in (
            ("ip", "IP address", 140), ("mac", "MAC", 180), ("hostname", "Hostname", 220),
            ("vendor", "Vendor hint", 140), ("ports", "Open ports", 200),
        ):
            self.lan_tree.heading(col, text=text)
            self.lan_tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.lan_tree.yview)
        self.lan_tree.configure(yscrollcommand=vsb.set)
        self.lan_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        vsb.grid(row=1, column=1, sticky="ns")

        ttk.Label(tab, text="Passive, non-invasive discovery via the system ARP cache. "
                            "Port probing is opt-in and limited to well-known service ports.",
                  style="Dim.TLabel", wraplength=800, justify="left").grid(row=2, column=0, sticky="w", pady=(6, 0))

    def _discover(self) -> None:
        scan_ports = self.discovery_ports_var.get()
        self.status("Discovering LAN devices...")
        self.run_in_thread(lambda: self._discovery_job(scan_ports), self._discovery_done)

    def _discovery_job(self, scan_ports: bool):
        from eis.modules.network.discovery import discover

        return discover(scan_ports=scan_ports)

    def _discovery_done(self, result) -> None:
        self.lan_tree.delete(*self.lan_tree.get_children())
        for dev in result.get("devices", []):
            self.lan_tree.insert("", "end", values=(
                dev.get("ip", ""), dev.get("mac", ""), dev.get("hostname") or "?",
                dev.get("vendor") or "", ", ".join(map(str, dev.get("open_ports", []))) if dev.get("open_ports") else "-",
            ))
        self.status(f"{result.get('count', 0)} devices found in {result.get('duration_s', '?')}s.")
