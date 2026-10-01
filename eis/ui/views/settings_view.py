"""Settings section: appearance, language, logging, safety, database, about."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from eis import APP_FULL_NAME, APP_LICENSE, APP_NAME, APP_VERSION
from eis.core.logging_config import get_log_path, setup_logging
from eis.core.settings import get_settings
from eis.ui.widgets import Card, OutputConsole, Section


class SettingsView(Section):
    label = "Settings"
    icon = "\u2699"

    def build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="ew")

        # --- Appearance ----------------------------------------------------
        appearance = Card(container, "Appearance")
        appearance.pack(fill="x", pady=(0, 8))
        row1 = ttk.Frame(appearance)
        row1.pack(anchor="w", pady=2)
        self.mode_var = tk.StringVar(value=self.settings.get("appearance.mode", "system"))
        ttk.Label(row1, text="Mode:").pack(side="left")
        ttk.Combobox(row1, textvariable=self.mode_var, width=10, state="readonly",
                     values=("light", "dark", "system")).pack(side="left", padx=4)
        ttk.Label(row1, text="Font size:").pack(side="left", padx=(14, 0))
        self.font_var = tk.StringVar(value=str(self.settings.get("appearance.font_size", 10)))
        ttk.Spinbox(row1, from_=8, to=16, textvariable=self.font_var, width=4).pack(side="left", padx=4)
        ttk.Button(row1, text="Apply", command=self._apply_appearance, style="Accent.TButton").pack(side="left", padx=10)

        # --- Language & logging ---------------------------------------------
        general = Card(container, "Language & logging")
        general.pack(fill="x", pady=(0, 8))
        row2 = ttk.Frame(general)
        row2.pack(anchor="w", pady=2)
        self.lang_var = tk.StringVar(value=self.settings.get("general.language", "en"))
        ttk.Label(row2, text="Language:").pack(side="left")
        ttk.Combobox(row2, textvariable=self.lang_var, width=8, state="readonly",
                     values=("en",)).pack(side="left", padx=4)
        self.log_level_var = tk.StringVar(value=self.settings.get("logging.level", "INFO"))
        ttk.Label(row2, text="   Log level:").pack(side="left")
        ttk.Combobox(row2, textvariable=self.log_level_var, width=8, state="readonly",
                     values=("DEBUG", "INFO", "WARNING", "ERROR")).pack(side="left", padx=4)
        self.console_log_var = tk.BooleanVar(value=self.settings.get("logging.console", True))
        ttk.Checkbutton(row2, text="Console output", variable=self.console_log_var).pack(side="left", padx=8)
        self.record_var = tk.BooleanVar(value=self.settings.get("logging.record_commands", True))
        ttk.Checkbutton(row2, text="Record command history", variable=self.record_var).pack(side="left")
        ttk.Button(general, text="Save logging settings", command=self._apply_logging).pack(anchor="w", pady=4)

        # --- Safety ------------------------------------------------------------
        safety = Card(container, "Safety engine")
        safety.pack(fill="x", pady=(0, 8))
        row3 = ttk.Frame(safety)
        row3.pack(anchor="w", pady=2)
        self.confirm_var = tk.BooleanVar(value=self.settings.get("safety.require_confirmation", True))
        ttk.Checkbutton(row3, text="Require confirmation for state-changing/destructive actions",
                        variable=self.confirm_var).pack(side="left")
        row4 = ttk.Frame(safety)
        row4.pack(anchor="w", pady=2)
        self.block_dirs_var = tk.BooleanVar(value=self.settings.get("safety.block_system_dirs", True))
        ttk.Checkbutton(row4, text="Protect system directories from cleaners/scanners",
                        variable=self.block_dirs_var).pack(side="left")
        ttk.Label(safety, text="Confirmation cannot be disabled for BLOCKED commands (format, diskpart, ...).",
                  style="Dim.TLabel").pack(anchor="w")

        # --- ADB paths ----------------------------------------------------------
        android = Card(container, "Android tools")
        android.pack(fill="x", pady=(0, 8))
        row5 = ttk.Frame(android)
        row5.pack(anchor="w", pady=2, fill="x")
        self.adb_var = tk.StringVar(value=self.settings.get("android.adb_path", ""))
        ttk.Label(row5, text="ADB path:").pack(side="left")
        ttk.Entry(row5, textvariable=self.adb_var, width=52).pack(side="left", padx=4)
        ttk.Button(row5, text="Auto-detect", command=self._detect_adb).pack(side="left")
        ttk.Button(android, text="Save paths", command=self._save_adb).pack(anchor="w", pady=4)

        # --- Database & history ---------------------------------------------------
        data_card = Card(container, "Database & history")
        data_card.pack(fill="x", pady=(0, 8))
        row6 = ttk.Frame(data_card)
        row6.pack(anchor="w", pady=2)
        ttk.Button(row6, text="Database info", command=self._db_info).pack(side="left")
        ttk.Button(row6, text="Backup database", command=self._db_backup).pack(side="left", padx=6)
        ttk.Button(row6, text="Open log folder", command=self._open_logs).pack(side="left", padx=6)
        ttk.Button(row6, text="Clear command history", command=self._clear_history,
                   style="Danger.TButton").pack(side="left", padx=6)

        # --- About ------------------------------------------------------------------
        about = Card(container, "About")
        about.pack(fill="x")
        ttk.Label(about, text=f"{APP_NAME} v{APP_VERSION} - {APP_FULL_NAME}\n"
                              f"License: {APP_LICENSE} - community edition, built for technicians.\n"
                              "Every module is open source and documented in docs/.",
                  justify="left").pack(anchor="w")

        # --- Log tail ---------------------------------------------------------------
        self.log_console = OutputConsole(self, height=10, save_name="eis_log_tail.txt")
        self.log_console.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        ttk.Label(self, text=f"Log file: {get_log_path()}", style="Dim.TLabel").grid(row=2, column=0, sticky="w")

    # ------------------------------------------------------------------
    @property
    def settings(self):
        return get_settings()

    def _apply_appearance(self) -> None:
        self.settings.set("appearance.mode", self.mode_var.get())
        try:
            size = max(8, min(16, int(self.font_var.get())))
        except ValueError:
            size = 10
        self.settings.set("appearance.font_size", size)
        self.settings.set("appearance.theme", "eis-dark" if self.mode_var.get() != "light" else "eis-light")
        if hasattr(self.app, "refresh_theme"):
            self.app.refresh_theme()
        self.status("Appearance updated.")

    def _apply_logging(self) -> None:
        self.settings.set("logging.level", self.log_level_var.get())
        self.settings.set("logging.console", self.console_log_var.get())
        self.settings.set("logging.record_commands", self.record_var.get())
        from eis.core.logging_config import set_console_logging

        root_logger = __import__("logging").getLogger()
        root_logger.setLevel(self.log_level_var.get())
        set_console_logging(self.console_log_var.get())
        self.status("Logging settings applied.")

    def _detect_adb(self) -> None:
        self.run_in_thread(self._adb_job, self._adb_done)

    def _adb_job(self):
        from eis.modules.android.adb import adb_path

        return adb_path()

    def _adb_done(self, path: str) -> None:
        if path:
            self.adb_var.set(path)
            self.settings.set("android.adb_path", path)
            self.status(f"ADB found: {path}")
        else:
            self.info("ADB", "ADB was not found. Install Android platform-tools and enter the path manually.")

    def _save_adb(self) -> None:
        self.settings.set("android.adb_path", self.adb_var.get().strip())
        self.status("ADB path saved.")

    def _db_info(self) -> None:
        self.run_in_thread(self._db_info_job, self._db_info_done)

    def _db_info_job(self):
        from eis.database.service import get_db

        return get_db().info()

    def _db_info_done(self, info) -> None:
        lines = [f"Schema version: {info['version']}", ""]
        for table, count in info["counts"].items():
            lines.append(f"  {table:<20} {count} rows")
        self.log_console.set_text("\n".join(lines))
        self.status("Database info loaded.")

    def _db_backup(self) -> None:
        self.run_in_thread(self._backup_job, self._backup_done)

    def _backup_job(self):
        from eis.database.service import get_db

        return str(get_db().backup())

    def _backup_done(self, path: str) -> None:
        self.log_console.append(f"Backup written: {path}")
        self.status("Database backup created.")

    def _open_logs(self) -> None:
        import os

        from eis.core.logging_config import LOG_DIR

        os.startfile(LOG_DIR)  # noqa: S606

    def _clear_history(self) -> None:
        if not self.confirm("Clear history",
                            "Delete the recorded command history (JSONL + database rows)?"):
            return
        from eis.core.paths import clear_history
        from eis.database.service import get_db

        removed_jsonl = clear_history()
        removed_db = get_db().command_history._conn().execute("DELETE FROM command_history").rowcount
        get_db().command_history._conn().commit()
        self.log_console.append(f"Cleared {removed_jsonl} JSONL entries and {removed_db} DB rows.")
        self.status("Command history cleared.")

    def on_show(self) -> None:
        from eis.core.logging_config import get_app_log_tail

        self.log_console.set_text(get_app_log_tail(40))
