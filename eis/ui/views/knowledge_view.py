"""Knowledge section: troubleshooting search, entry detail, command history."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis.ui.widgets import OutputConsole, Section, ToolBar


class KnowledgeView(Section):
    label = "Knowledge"
    icon = "\U0001F4DA"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        bar = ToolBar(self)
        bar.grid(row=0, column=0, sticky="ew")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=42)
        entry.pack(side="left", padx=(0, 4))
        entry.bind("<Return>", lambda _e: self._search())
        self.cat_var = tk.StringVar(value="")
        ttk.Combobox(bar, textvariable=self.cat_var, width=16, state="readonly",
                     postcommand=self._refresh_categories).pack(side="left", padx=4)
        bar.add_button("Search", self._search, style="Accent.TButton")
        bar.add_button("Match pasted error", self._match_error)
        bar.add_button("Show all", lambda: self.search_var.set("") or self._search())

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        left = ttk.Frame(paned)
        self.kb_tree = ttk.Treeview(left, columns=("id", "title", "sev"), show="headings", height=20)
        self.kb_tree.heading("id", text="ID")
        self.kb_tree.heading("title", text="Title")
        self.kb_tree.heading("sev", text="Severity")
        self.kb_tree.column("id", width=150, anchor="w")
        self.kb_tree.column("title", width=380, anchor="w")
        self.kb_tree.column("sev", width=80, anchor="center")
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.kb_tree.yview)
        self.kb_tree.configure(yscrollcommand=vsb.set)
        self.kb_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.kb_tree.bind("<<TreeviewSelect>>", lambda _e: self._show_entry())
        paned.add(left, weight=3)

        right = ttk.Frame(paned)
        self.detail = OutputConsole(right, height=24, save_name="kb_entry.txt")
        self.detail.pack(fill="both", expand=True)
        feedback = ttk.Frame(right)
        feedback.pack(fill="x", pady=(4, 0))
        ttk.Button(feedback, text="This helped",
                   command=lambda: self._rate(True)).pack(side="left")
        ttk.Button(feedback, text="Did not help",
                   command=lambda: self._rate(False)).pack(side="left", padx=6)
        paned.add(right, weight=2)

        self._entries: list[dict] = []
        self._search()

    def _refresh_categories(self) -> None:
        from eis.modules.knowledge.kb import categories_present

        values = [""] + categories_present()
        widget = self.kb_tree.master.master  # toolbar combobox lookup simplification
        self.cat_box = None
        for child in self.winfo_children():
            if isinstance(child, ToolBar):
                for w in child.winfo_children():
                    if isinstance(w, ttk.Combobox):
                        self.cat_box = w
        if self.cat_box is not None:
            self.cat_box["values"] = values

    def _search(self) -> None:
        query = self.search_var.get().strip()
        category = self.cat_var.get()
        self.run_in_thread(lambda: self._search_job(query, category), self._search_done)

    def _search_job(self, query: str, category: str):
        from eis.modules.knowledge.kb import search

        return search(query, category=category)

    def _search_done(self, results) -> None:
        self._entries = results
        self.kb_tree.delete(*self.kb_tree.get_children())
        for e in results:
            rel = f"  ({e['relevance']})" if e.get("relevance") else ""
            self.kb_tree.insert("", "end", values=(e["id"], e["title"][:70] + rel, e.get("severity", "")))
        self.status(f"{len(results)} knowledge base entries.")

    def _match_error(self) -> None:
        text = tk.simpledialog.askstring(  # type: ignore[attr-defined]
            "Match error", "Paste the error text or log line:", parent=self
        ) if False else self._ask_text()
        if not text:
            return
        self.run_in_thread(lambda: self._match_job(text), self._search_done)

    def _ask_text(self) -> str:
        import tkinter.simpledialog

        return tkinter.simpledialog.askstring("Match error", "Paste the error text or log line:", parent=self) or ""

    def _match_job(self, text: str):
        from eis.modules.knowledge.kb import match_error_text

        return match_error_text(text)

    def _show_entry(self) -> None:
        sel = self.kb_tree.selection()
        if not sel:
            return
        idx = self.kb_tree.index(sel[0])
        if idx >= len(self._entries):
            return
        e = self._entries[idx]
        lines = [
            f"{e['title']}",
            f"Category: {e.get('category', '')}   Severity: {e.get('severity', '')}   OS: {e.get('os', '')}",
            "",
            "SYMPTOMS",
            *[f"  - {s}" for s in e.get("symptoms", [])],
            "",
            "LIKELY CAUSES",
            *[f"  - {c}" for c in e.get("causes", [])],
            "",
            "DIAGNOSTIC STEPS",
            *[f"  {i}. {d}" for i, d in enumerate(e.get("diagnostics", []), start=1)],
            "",
            "SOLUTIONS (safest first)",
            *[f"  {i}. {s}" for i, s in enumerate(e.get("solutions", []), start=1)],
        ]
        if e.get("matched_patterns"):
            lines.insert(2, f"Matched patterns: {', '.join(e['matched_patterns'])}")
        if e.get("references"):
            lines += ["", "REFERENCES", *[f"  - {r}" for r in e["references"]]]
        lines += ["", f"[{e['id']}]"]
        self.detail.set_text("\n".join(lines))

    def _rate(self, helpful: bool) -> None:
        sel = self.kb_tree.selection()
        if not sel:
            return
        idx = self.kb_tree.index(sel[0])
        if idx >= len(self._entries):
            return
        kb_id = self._entries[idx]["id"]
        try:
            from eis.database.service import get_db

            get_db().kb_feedback.rate(kb_id, helpful)
            self.status("Thanks - feedback recorded.")
        except Exception as exc:  # pragma: no cover
            self.status(f"Feedback not saved: {exc}")
