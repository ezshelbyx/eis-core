"""E.I.S. Core dashboard shell: Tkinter root window, sidebar, section host."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from eis import APP_NAME, APP_TAGLINE, APP_VERSION
from eis.core.logging_config import setup_logging
from eis.core.settings import get_settings
from eis.core.utils import app_title
from eis.ui.theme import palette
from eis.ui.widgets import StatusBar

log = logging.getLogger(__name__)


class EISApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.title(app_title())
        self.minsize(1000, 640)

        self._section_defs: list[tuple[str, str, type]] = []
        self._sections: dict[str, object] = {}
        self._nav_buttons: dict[str, ttk.Button] = {}
        self._current: str = ""
        self._pump_job: str | None = None

        self._collect_sections()
        self._build_layout()
        self._apply_theme()
        self._bind_keys()

        # Restore geometry
        geometry = self.settings.get("appearance.window_geometry", "1280x800")
        try:
            self.geometry(geometry)
        except tk.TclError:
            pass
        if self.settings.get("appearance.window_maximized", True):
            self.state("zoomed") if self._supports_zoom() else None

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_section("system")
        self._pump_results()
        log.info("%s %s started", APP_NAME, APP_VERSION)

    # ------------------------------------------------------------------
    def _supports_zoom(self) -> bool:
        try:
            self.state("zoomed")
            return True
        except tk.TclError:
            return False

    def _collect_sections(self) -> None:
        """Import section views lazily to keep startup fast."""
        from eis.ui.views.android_view import AndroidView
        from eis.ui.views.diagnostics_view import DiagnosticsView
        from eis.ui.views.files_view import FilesView
        from eis.ui.views.knowledge_view import KnowledgeView
        from eis.ui.views.network_view import NetworkView
        from eis.ui.views.repair_view import RepairView
        from eis.ui.views.settings_view import SettingsView
        from eis.ui.views.system_view import SystemView

        self._section_defs = [
            ("system", "System", SystemView),
            ("diagnostics", "Diagnostics", DiagnosticsView),
            ("repair", "Repair", RepairView),
            ("android", "Android", AndroidView),
            ("network", "Network", NetworkView),
            ("files", "Files", FilesView),
            ("knowledge", "Knowledge", KnowledgeView),
            ("settings", "Settings", SettingsView),
        ]

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # --- Header -----------------------------------------------------
        header = ttk.Frame(self, padding=(10, 8))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, text=APP_NAME, font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Label(header, text=APP_TAGLINE, foreground=self._dim()).pack(side="left", padx=10)
        ttk.Label(header, text=f"v{APP_VERSION}").pack(side="right")

        # --- Sidebar ------------------------------------------------------
        self.sidebar = ttk.Frame(self, padding=8)
        self.sidebar.grid(row=1, column=0, sticky="ns")
        for key, label, _cls in self._section_defs:
            btn = ttk.Button(
                self.sidebar, text=f"  {label}", width=14, style="Side.TButton",
                command=lambda k=key: self.show_section(k),
            )
            btn.pack(fill="x", pady=2, ipady=4)
            self._nav_buttons[key] = btn
        self.sidebar.columnconfigure(0, weight=1)

        # --- Content host ---------------------------------------------------
        self.content = ttk.Frame(self, padding=10)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        # --- Status bar ------------------------------------------------------
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")

    # ------------------------------------------------------------------
    def show_section(self, key: str) -> None:
        if key == self._current:
            return
        definition = next((d for d in self._section_defs if d[0] == key), None)
        if not definition:
            return
        _key, _label, view_cls = definition

        # Hide current
        for child in self.content.winfo_children():
            child.grid_forget()

        view = self._sections.get(key)
        if view is None:
            view = view_cls(self.content, app=self)
            self._sections[key] = view
        view.grid(row=0, column=0, sticky="nsew")
        view.rowconfigure(0, weight=1)
        view.columnconfigure(0, weight=1)
        view.build_once()
        if hasattr(view, "on_show"):
            view.on_show()

        self._current = key
        # Nav highlight
        for k, btn in self._nav_buttons.items():
            btn.configure(style="Side.TButton" if k != key else "SideActive.TButton")
        self.set_status(f"{_label} section")

    def set_status(self, text: str, badge: str = "") -> None:
        self.status_bar.set(text, badge)

    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        pal = palette()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover
            pass

        self.configure(bg=pal["bg"])
        style.configure(".", background=pal["bg"], foreground=pal["fg"], font=("Segoe UI", font_pt()))
        style.configure("TFrame", background=pal["bg"])
        style.configure("TLabel", background=pal["bg"], foreground=pal["fg"])
        style.configure("Dim.TLabel", background=pal["bg"], foreground=pal["fg_dim"])
        style.configure("Header.TLabel", background=pal["bg"], font=("Segoe UI", 12, "bold"))

        style.configure("TLabelframe", background=pal["bg_panel"], bordercolor=pal["border"])
        style.configure("TLabelframe.Label", background=pal["bg_panel"], foreground=pal["accent"],
                        font=("Segoe UI", font_pt(), "bold"))
        style.configure("TButton", background=pal["bg_input"], foreground=pal["fg"],
                        bordercolor=pal["border"], padding=(8, 4))
        style.map("TButton",
                  background=[("active", pal["bg_hover"]), ("disabled", pal["bg_panel"])],
                  foreground=[("disabled", pal["fg_dim"])])
        style.configure("Accent.TButton", background=pal["accent"], foreground=pal["accent_fg"])
        style.map("Accent.TButton", background=[("active", pal["select"]), ("disabled", pal["bg_hover"])])
        style.configure("Danger.TButton", background=pal["danger"], foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#c0392b"), ("disabled", pal["bg_hover"])])

        style.configure("Side.TButton", anchor="w", background=pal["bg_panel"],
                        foreground=pal["fg"], padding=(10, 2))
        style.map("Side.TButton", background=[("active", pal["bg_hover"])])
        style.configure("SideActive.TButton", anchor="w", background=pal["accent"],
                        foreground=pal["accent_fg"], padding=(10, 2))

        style.configure("TEntry", fieldbackground=pal["bg_input"], foreground=pal["fg"],
                        insertcolor=pal["fg"], bordercolor=pal["border"])
        style.configure("TCombobox", fieldbackground=pal["bg_input"], foreground=pal["fg"],
                        background=pal["bg_input"], bordercolor=pal["border"])
        style.configure("TSpinbox", fieldbackground=pal["bg_input"], foreground=pal["fg"],
                        bordercolor=pal["border"])
        style.map("TSpinbox", fieldbackground=[("readonly", pal["bg_input"])])

        style.configure("Treeview", background=pal["bg_input"], foreground=pal["fg"],
                        fieldbackground=pal["bg_input"], bordercolor=pal["border"], rowheight=22)
        style.map("Treeview",
                  background=[("selected", pal["select"])],
                  foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=pal["bg_panel"], foreground=pal["fg_dim"],
                        font=("Segoe UI", font_pt(), "bold"))
        style.configure("TScrollbar", background=pal["bg_input"], bordercolor=pal["bg"],
                        arrowcolor=pal["fg_dim"], troughcolor=pal["bg"])
        style.configure("TProgressbar", background=pal["accent"], troughcolor=pal["bg_input"],
                        bordercolor=pal["bg"])
        style.configure("Status.TFrame", background=pal["bg_panel"])
        style.configure("Status.TLabel", background=pal["bg_panel"], foreground=pal["fg_dim"])

        self.status_bar.configure(style="Status.TFrame")
        self.sidebar.configure(style="TFrame")

        # Recolor open Text widgets
        for view in self._sections.values():
            for text in view.winfo_children():
                pass  # views handle their own Text widgets in apply_theme()

    def refresh_theme(self) -> None:
        self._apply_theme()

    def _dim(self) -> str:
        return palette()["fg_dim"]

    # ------------------------------------------------------------------
    def _bind_keys(self) -> None:
        self.bind("<F5>", lambda _e: self._refresh_current())
        for i, (key, _label, _cls) in enumerate(self._section_defs, start=1):
            self.bind(f"<F{i}>", lambda _e, k=key: self.show_section(k))

    def _refresh_current(self) -> None:
        view = self._sections.get(self._current)
        if view is not None and hasattr(view, "refresh"):
            view.refresh()
            self.set_status("Refreshed.")

    def _pump_results(self) -> None:
        """Deliver background-thread results to the UI thread, every 100 ms."""
        for view in list(self._sections.values()):
            pump = getattr(view, "pump_results", None)
            if callable(pump):
                pump()
        self._pump_job = self.after(100, self._pump_results)

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        try:
            maximized = self.state() == "zoomed"
            self.settings.set("appearance.window_maximized", maximized, save=False)
            if not maximized:
                self.settings.set("appearance.window_geometry", self.geometry(), save=False)
            self.settings.save()
        except Exception:  # pragma: no cover
            pass
        log.info("Application closed.")
        self.destroy()


def font_pt() -> int:
    from eis.ui.theme import font_size

    return font_size()


def main() -> None:
    settings = get_settings()
    setup_logging(level=settings.get("logging.level"), console=settings.get("logging.console", True))
    app = EISApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
