"""Reusable Tkinter building blocks for E.I.S. Core views.

Kept deliberately dependency-free: ttk styling plus a few composite widgets
(cards, key/value tables, output console, progress helper) used by all views.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from eis.ui.theme import palette


class Card(ttk.LabelFrame):
    """Titled panel used as the base unit of every view."""

    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, text=f" {title} ", padding=8, **kwargs)


class KVTable(ttk.Frame):
    """Two-column key/value table with monospaced values and copy support."""

    def __init__(self, master, columns=("Property", "Value"), height: int = 14):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=height)
        self.tree.heading(0, text=columns[0])
        self.tree.heading(1, text=columns[1])
        self.tree.column(0, width=220, anchor="w", stretch=False)
        self.tree.column(1, width=520, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._copy_cell)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        self.tree.delete(*self.tree.get_children())
        for k, v in rows:
            self.tree.insert("", "end", values=(k, v))

    def _copy_cell(self, _event) -> str:
        sel = self.tree.selection()
        if sel:
            values = self.tree.item(sel[0], "values")
            if values:
                self.clipboard_clear()
                self.clipboard_append(values[-1])
        return "break"


class OutputConsole(ttk.Frame):
    """Read-only monospaced console for command output, with copy + save."""

    def __init__(self, master, height: int = 16, save_name: str = "eis_output.txt"):
        super().__init__(master)
        self.save_name = save_name
        self.text = tk.Text(
            self, height=height, wrap="word", state="disabled",
            font=("Consolas", max(9, palette_font())),
        )
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(bar, text="Copy all", width=10, command=self.copy_all).pack(side="left")
        ttk.Button(bar, text="Save as...", width=12, command=self.save_as).pack(side="left", padx=6)
        ttk.Button(bar, text="Clear", width=8, command=self.clear).pack(side="left")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def append(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text if text.endswith("\n") else text + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def set_text(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")

    def get_text(self) -> str:
        return self.text.get("1.0", "end").rstrip("\n")

    def clear(self) -> None:
        self.set_text("")

    def copy_all(self) -> None:
        text = self.get_text()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def save_as(self) -> None:
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=self.save_name,
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.get_text())
            except OSError as exc:
                messagebox.showerror("Save failed", str(exc))


def palette_font() -> int:
    from eis.ui.theme import font_size

    return font_size()


class StatusBar(ttk.Frame):
    """Bottom bar: status message left, live indicators right."""

    def __init__(self, master):
        super().__init__(master, padding=(8, 4))
        self.message = tk.StringVar(value="Ready.")
        self.message_label = ttk.Label(self, textvariable=self.message, anchor="w", style="Status.TLabel")
        self.message_label.pack(side="left", fill="x", expand=True)
        self.badge_var = tk.StringVar(value="")
        self.badge = ttk.Label(self, textvariable=self.badge_var, anchor="e", style="Status.TLabel")
        self.badge.pack(side="right")

    def set(self, text: str, badge: str = "") -> None:
        self.message.set(text)
        if badge:
            self.badge_var.set(badge)


class ToolBar(ttk.Frame):
    """Row of buttons + optional entry, used at the top of views."""

    def __init__(self, master):
        super().__init__(master)
        self._buttons: dict[str, ttk.Button] = {}

    def add_button(self, text: str, command: Callable, side: str = "left",
                   name: str | None = None, style: str | None = None) -> ttk.Button:
        btn = ttk.Button(self, text=text, command=command, style=style)
        btn.pack(side=side, padx=(0, 6), pady=4)
        if name:
            self._buttons[name] = btn
        return btn

    def add_entry(self, name: str, width: int = 28, default: str = "") -> ttk.Entry:
        var = tk.StringVar(value=default)
        entry = ttk.Entry(self, textvariable=var, width=width)
        entry.pack(side="left", padx=(0, 6), pady=4)
        entry.var = var  # type: ignore[attr-defined]
        self._buttons[name] = entry  # reuse retrieval
        return entry

    def get(self, name: str) -> str:
        widget = self._buttons.get(name)
        if widget is None:
            return ""
        var = getattr(widget, "var", None)
        if var is not None:
            return var.get()
        return ""

    def set_enabled(self, name: str, enabled: bool) -> None:
        widget = self._buttons.get(name)
        if isinstance(widget, ttk.Button):
            state = "normal" if enabled else "disabled"
            widget.configure(state=state)


class Section(ttk.Frame):
    """Base class for dashboard section views.

    Subclasses implement ``refresh()`` and optional ``on_show()``.
    """

    label = "Section"
    icon = "\u25a4"

    def __init__(self, master, app: Any, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._built = False
        self._pending: list[tuple[Callable, Any]] = []

    def build_once(self) -> None:
        if not self._built:
            self.build()
            self._built = True

    def build(self) -> None:  # pragma: no cover - implemented by subclasses
        ttk.Label(self, text="Not implemented").pack(pady=20)

    def refresh(self) -> None:  # pragma: no cover - implemented by subclasses
        pass

    def on_show(self) -> None:
        self.refresh()

    # -- helpers available to subclasses -----------------------------------
    def run_in_thread(self, func: Callable[[], Any], on_done: Callable[[Any], None],
                      on_error: Callable[[Exception], None] | None = None) -> None:
        """Run blocking work off the UI thread.

        Results are queued and pumped by ``pump_results()`` on the main loop
        (Tk ``after`` is not safely callable from worker threads).
        """
        import queue
        import threading

        result_queue: "queue.Queue[tuple[bool, Any]]" = queue.Queue()

        def worker():
            try:
                result_queue.put((True, func()))
            except Exception as exc:  # pragma: no cover
                result_queue.put((False, exc))

        threading.Thread(target=worker, daemon=True).start()
        self._pending.append((self._make_pump(result_queue, on_done, on_error), None))

    def _make_pump(self, result_queue, on_done, on_error):
        def pump() -> None:
            import queue as _queue

            try:
                ok, result = result_queue.get_nowait()
            except _queue.Empty:
                self.after(80, pump)
                return
            if ok:
                on_done(result)
            elif on_error:
                on_error(result)

        return pump

    def pump_results(self) -> None:
        """Start pending result pumps (called by the app loop)."""
        while self._pending:
            pump, _payload = self._pending.pop(0)
            self.after(1, pump)

    def status(self, text: str) -> None:
        if hasattr(self.app, "set_status"):
            self.app.set_status(text)

    def confirm(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def ask_open_path(self, **kwargs) -> str:
        return filedialog.askopenfilename(**kwargs)

    def ask_open_dir(self, **kwargs) -> str:
        return filedialog.askdirectory(**kwargs)

    def apply_theme(self) -> None:
        """Re-apply colors when the theme changes (override in subclasses)."""
        pal = palette()
        style = ttk.Style(self)
        style.configure("Card.TLabelframe", background=pal["bg_panel"])
