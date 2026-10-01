"""
E.I.S. Core (Electronic Intelligence & Service Core)
=====================================================

A lightweight, community-focused technician, diagnostic, repair and utility
platform for Windows.

Built with Python, Tkinter, SQLite and JSON.  Designed to run comfortably on
low-end hardware: every dependency is optional and every module degrades
gracefully when a capability (e.g. ``psutil``) is unavailable.

Package layout::

    eis/
      core/       - utilities shared by every module (config, logging, safety...)
      database/   - SQLite schema + repositories (customers, devices, jobs...)
      modules/    - feature modules (system, windows, network, android...)
      ui/         - Tkinter dashboard and section views

This file is the single source of truth for the application identity.
"""

from __future__ import annotations

APP_NAME = "E.I.S. Core"
APP_FULL_NAME = "Electronic Intelligence & Service Core"
APP_TAGLINE = "Technician, Diagnostic, Repair & Utility Platform"
APP_VERSION = "0.1.0"
APP_AUTHOR = "E.I.S. Community"
APP_HOMEPAGE = "https://github.com/eis-community/eis-core"
APP_LICENSE = "MIT"
APP_COPYRIGHT = "2026 E.I.S. Community"

# Bumped whenever the SQLite schema or the settings defaults change so that
# `python -m eis.bootstrap` can upgrade existing installations.
APP_BUILD = 1

__all__ = [
    "APP_NAME",
    "APP_FULL_NAME",
    "APP_TAGLINE",
    "APP_VERSION",
    "APP_AUTHOR",
    "APP_HOMEPAGE",
    "APP_LICENSE",
    "APP_COPYRIGHT",
    "APP_BUILD",
]
