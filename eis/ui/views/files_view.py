"""Files section: hashing, duplicates, metadata, passwords, QR payloads."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.core.utils import format_bytes, safe_filename
from eis.ui.widgets import Card, OutputConsole, Section, ToolBar


class FilesView(Section):
    label = "Files"
    icon = "\U0001F4C1"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._build_hash_tab(notebook)
        self._build_duplicates_tab(notebook)
        self._build_metadata_tab(notebook)
        self._build_password_tab(notebook)
        self._build_qr_tab(notebook)

    # -- hashing ---------------------------------------------------------------
    def _build_hash_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" File hashing ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Choose file...", self._choose_hash_file)
        self.hash_file_var = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self.hash_file_var, width=52).pack(side="left", padx=4)
        self.hash_algo_var = tk.StringVar(value="sha256")
        ttk.Combobox(bar, textvariable=self.hash_algo_var, width=8, state="readonly",
                     values=("md5", "sha1", "sha256", "sha512")).pack(side="left", padx=4)
        bar.add_button("Hash", self._do_hash, style="Accent.TButton")
        self.expected_var = tk.StringVar()
        ttk.Label(bar, text="Expected:").pack(side="left")
        ttk.Entry(bar, textvariable=self.expected_var, width=34).pack(side="left", padx=4)
        bar.add_button("Verify", self._do_verify)

        self.hash_console = OutputConsole(tab, height=18, save_name="hashes.txt")
        self.hash_console.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def _choose_hash_file(self) -> None:
        path = self.ask_open_path(filetypes=[("All files", "*.*")])
        if path:
            self.hash_file_var.set(path)

    def _do_hash(self) -> None:
        path = self.hash_file_var.get().strip()
        if not path:
            self.info("Hash", "Choose a file first.")
            return
        algo = self.hash_algo_var.get()
        self.run_in_thread(lambda: self._hash_job(path, ("md5", "sha1", "sha256", "sha512")), self._hash_done)

    def _hash_job(self, path: str, algos):
        from eis.modules.files.hashing import hash_file

        return hash_file(path, algos)

    def _hash_done(self, result) -> None:
        if not result.get("ok"):
            self.hash_console.append(f"Error: {result.get('error')}")
            return
        lines = [f"File: {result['file']} ({format_bytes(result['size'])})"]
        for algo, digest in result["hashes"].items():
            lines.append(f"  {algo.upper():<7}: {digest}")
        self.hash_console.append("\n".join(lines) + "\n")
        self.status("Hashing complete.")

    def _do_verify(self) -> None:
        path = self.hash_file_var.get().strip()
        expected = self.expected_var.get().strip()
        if not path or not expected:
            self.info("Verify", "Choose a file and paste the expected hash.")
            return
        algo = self.hash_algo_var.get()
        self.run_in_thread(lambda: self._verify_job(path, expected, algo), self._verify_done)

    def _verify_job(self, path: str, expected: str, algo: str):
        from eis.modules.files.hashing import verify_file

        return verify_file(path, expected, algo)

    def _verify_done(self, result) -> None:
        self.hash_console.append(
            f"{result.get('verdict', result.get('error', ''))}\n"
            f"  expected: {result.get('expected', '')}\n  actual:   {result.get('actual', '')}\n"
        )

    # -- duplicates ----------------------------------------------------------------
    def _build_duplicates_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        parent.add(tab, text=" Duplicate finder ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Choose folder...", self._choose_dup_dir)
        self.dup_dir_var = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self.dup_dir_var, width=50).pack(side="left", padx=4)
        bar.add_button("Find duplicates", self._find_dups, style="Accent.TButton")
        ttk.Label(tab, text="System and user-document folders are protected and refused by the safety engine.",
                  style="Dim.TLabel").grid(row=0, column=0, sticky="ew", pady=(26, 2))

        self.dup_console = OutputConsole(tab, height=18, save_name="duplicates.txt")
        self.dup_console.grid(row=1, column=0, sticky="nsew", pady=(2, 0))

    def _choose_dup_dir(self) -> None:
        path = self.ask_open_dir()
        if path:
            self.dup_dir_var.set(path)

    def _find_dups(self) -> None:
        root = self.dup_dir_var.get().strip()
        if not root:
            self.info("Duplicates", "Choose a folder to scan.")
            return
        self.status("Scanning for duplicates (size + partial + full hash)...")
        self.run_in_thread(lambda: self._dup_job(root), self._dup_done)

    def _dup_job(self, root: str):
        from eis.modules.files.duplicates import find_duplicates

        return find_duplicates([root])

    def _dup_done(self, result) -> None:
        lines = [
            f"Scanned       : {result['scanned_files']} files",
            f"Duplicate sets: {result['duplicate_groups']}",
            f"Wasted space  : {result['wasted_human']}",
        ]
        for blocked in result.get("blocked_roots", []):
            lines.append(f"BLOCKED: {blocked['root']} ({blocked['reason']})")
        lines.append("")
        for group in result.get("groups", []):
            lines.append(f"[{format_bytes(group['size'])}] {group['hash_key']}")
            for f in group["files"]:
                lines.append(f"    {f}")
        self.dup_console.set_text("\n".join(lines))
        self.status("Duplicate scan complete.")

    # -- metadata --------------------------------------------------------------------
    def _build_metadata_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Metadata ")

        bar = ToolBar(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.add_button("Choose file/folder...", self._choose_meta_path)
        self.meta_path_var = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self.meta_path_var, width=56).pack(side="left", padx=4)
        bar.add_button("Inspect", self._inspect, style="Accent.TButton")

        self.meta_console = OutputConsole(tab, height=18, save_name="metadata.txt")
        self.meta_console.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def _choose_meta_path(self) -> None:
        path = self.ask_open_path(filetypes=[("All files", "*.*")])
        if path:
            self.meta_path_var.set(path)

    def _inspect(self) -> None:
        path = self.meta_path_var.get().strip()
        if not path:
            return
        self.run_in_thread(lambda: self._meta_job(path), self._meta_done)

    def _meta_job(self, path: str):
        from eis.modules.files.metadata import inspect

        return inspect(path)

    def _meta_done(self, result) -> None:
        if not result.get("ok"):
            self.meta_console.append(f"Error: {result.get('error')}")
            return
        lines = [
            f"Path      : {result['path']}",
            f"Type      : {result['type']}   Extension: {result.get('extension') or '-'}",
            f"Size      : {format_bytes(result['size_bytes'])}",
            f"Created   : {result['created']}",
            f"Modified  : {result['modified']}",
            f"Accessed  : {result['accessed']}",
            f"Attributes: {result.get('attributes', '')}   Hidden: {result.get('hidden')}   "
            f"ReadOnly: {result.get('read_only')}",
        ]
        for algo, digest in (result.get("hashes") or {}).items():
            lines.append(f"Hash {algo.upper():<4}: {digest}")
        self.meta_console.append("\n".join(lines) + "\n")

    # -- passwords ----------------------------------------------------------------------
    def _build_password_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" Password generator ")

        card = Card(tab, "Options")
        card.pack(fill="x")
        row1 = ttk.Frame(card)
        row1.pack(anchor="w", pady=2)
        ttk.Label(row1, text="Length:").pack(side="left")
        self.pw_len_var = tk.StringVar(value="20")
        ttk.Spinbox(row1, from_=4, to=256, textvariable=self.pw_len_var, width=5).pack(side="left", padx=6)
        self.pw_lower = tk.BooleanVar(value=True)
        self.pw_upper = tk.BooleanVar(value=True)
        self.pw_digits = tk.BooleanVar(value=True)
        self.pw_symbols = tk.BooleanVar(value=True)
        self.pw_no_ambig = tk.BooleanVar(value=True)
        for text, var in (
            ("a-z", self.pw_lower), ("A-Z", self.pw_upper), ("0-9", self.pw_digits),
            ("symbols", self.pw_symbols), ("no ambiguous", self.pw_no_ambig),
        ):
            ttk.Checkbutton(row1, text=text, variable=var).pack(side="left", padx=4)
        row2 = ttk.Frame(card)
        row2.pack(anchor="w", pady=4)
        ttk.Button(row2, text="Generate password", command=self._gen_password, style="Accent.TButton").pack(side="left")
        ttk.Label(row2, text="   Words:").pack(side="left")
        self.pp_words_var = tk.StringVar(value="4")
        ttk.Spinbox(row2, from_=2, to=12, textvariable=self.pp_words_var, width=4).pack(side="left", padx=4)
        ttk.Button(row2, text="Generate passphrase", command=self._gen_passphrase).pack(side="left")

        self.pw_console = OutputConsole(tab, height=12, save_name="passwords.txt")
        self.pw_console.pack(fill="both", expand=True, pady=(6, 0))
        ttk.Label(tab, text="Generated with the cryptographically secure 'secrets' module. "
                            "Passwords are never logged or written to disk.",
                  style="Dim.TLabel").pack(anchor="w", pady=(4, 0))

    def _gen_password(self) -> None:
        try:
            length = int(self.pw_len_var.get())
        except ValueError:
            length = 20
        self.run_in_thread(
            lambda: self._pw_job(length, self.pw_lower.get(), self.pw_upper.get(),
                                 self.pw_digits.get(), self.pw_symbols.get(), self.pw_no_ambig.get()),
            self._pw_done,
        )

    def _pw_job(self, length, lower, upper, digits, symbols, no_ambig):
        from eis.modules.files.generators import generate_password

        return generate_password(length, lower, upper, digits, symbols, no_ambig)

    def _pw_done(self, result) -> None:
        if result.get("ok"):
            self.pw_console.append(f"{result['password']}   ({result['length']} chars, "
                                   f"{result['entropy_bits']} bits, {result['strength']})")
        else:
            self.error("Password", result.get("error", "Failed."))

    def _gen_passphrase(self) -> None:
        try:
            words = int(self.pp_words_var.get())
        except ValueError:
            words = 4
        self.run_in_thread(lambda: self._pp_job(words), self._pp_done)

    def _pp_job(self, words: int):
        from eis.modules.files.generators import generate_passphrase

        return generate_passphrase(words=words)

    def _pp_done(self, result) -> None:
        if result.get("ok"):
            self.pw_console.append(f"{result['passphrase']}   ({result['entropy_bits']} bits, {result['strength']})")
        else:
            self.error("Passphrase", result.get("error", "Failed."))

    # -- QR payloads ----------------------------------------------------------------------
    def _build_qr_tab(self, parent) -> None:
        tab = ttk.Frame(parent, padding=6)
        tab.columnconfigure(0, weight=1)
        parent.add(tab, text=" QR generator ")

        card = Card(tab, "QR payload (Wi-Fi, URL, text, technician card)")
        card.pack(fill="x")

        row = ttk.Frame(card)
        row.pack(anchor="w", pady=2)
        self.qr_kind_var = tk.StringVar(value="wifi")
        ttk.Label(row, text="Type:").pack(side="left")
        ttk.Combobox(row, textvariable=self.qr_kind_var, width=10, state="readonly",
                     values=("wifi", "url", "text", "vcard")).pack(side="left", padx=4)
        ttk.Label(row, text="SSID/Name:").pack(side="left")
        self.qr_field1 = tk.StringVar()
        ttk.Entry(row, textvariable=self.qr_field1, width=22).pack(side="left", padx=4)
        ttk.Label(row, text="Password/Phone:").pack(side="left")
        self.qr_field2 = tk.StringVar()
        ttk.Entry(row, textvariable=self.qr_field2, width=22).pack(side="left", padx=4)
        ttk.Label(row, text="Extra (URL/note):").pack(side="left")
        self.qr_field3 = tk.StringVar()
        ttk.Entry(row, textvariable=self.qr_field3, width=22).pack(side="left", padx=4)

        row2 = ttk.Frame(card)
        row2.pack(anchor="w", pady=4)
        ttk.Button(row2, text="Build payload", command=self._build_qr, style="Accent.TButton").pack(side="left")
        ttk.Button(row2, text="Open QR in browser", command=self._show_qr).pack(side="left", padx=6)
        ttk.Label(row2, text="(renders locally in your browser - no network call)",
                  style="Dim.TLabel").pack(side="left")

        self.qr_output = OutputConsole(tab, height=8, save_name="qr_payload.txt")
        self.qr_output.pack(fill="both", expand=True, pady=(6, 0))
        self._qr_payload: str = ""

    def _build_qr(self) -> None:
        kind = self.qr_kind_var.get()
        f1, f2, f3 = self.qr_field1.get(), self.qr_field2.get(), self.qr_field3.get()
        self.run_in_thread(lambda: self._qr_job(kind, f1, f2, f3), self._qr_done)

    def _qr_job(self, kind: str, f1: str, f2: str, f3: str):
        from eis.modules.files.generators import text_payload, url_payload, vcard_payload, wifi_payload

        if kind == "wifi":
            return wifi_payload(f1, f2)
        if kind == "url":
            return url_payload(f3 or f1)
        if kind == "vcard":
            return vcard_payload(f1 or "Technician", org="E.I.S.", phone=f2, note=f3)
        return text_payload(f3 or f1)

    def _qr_done(self, payload: str) -> None:
        self._qr_payload = payload
        self.qr_output.set_text(payload)

    def _show_qr(self) -> None:
        if not self._qr_payload:
            self._build_qr()
        if not self._qr_payload:
            self.info("QR", "Build a payload first.")
            return
        import html
        import tempfile
        import webbrowser
        from pathlib import Path

        from eis.core.logging_config import REPORT_DIR

        payload = html.escape(self._qr_payload)
        template = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>E.I.S. QR</title>"
            "<script src='https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js'></script>"
            "</head><body style='font-family:sans-serif;text-align:center;padding-top:30px'>"
            "<div id='q'></div><p>" + payload + "</p>"
            "<script>new QRCode(document.getElementById('q'), {text:\"" +
            self._qr_payload.replace('"', '\\"').replace("\n", "\\n") + "\", width: 320, height: 320});</script>"
            "</body></html>"
        )
        out = REPORT_DIR / "qr_preview.html"
        out.write_text(template, encoding="utf-8")
        webbrowser.open(out.as_uri())
