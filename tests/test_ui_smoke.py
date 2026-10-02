"""Headless UI smoke test: the dashboard must build and open all 8 sections.

These tests require a display.  On Windows they run natively; on Linux CI a
virtual display (Xvfb) is needed.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")

SECTIONS = ["system", "diagnostics", "repair", "android", "network", "files", "knowledge", "settings"]


@pytest.fixture(scope="module")
def app():
    from eis.ui.app import EISApp

    instance = EISApp()
    instance.update_idletasks()
    yield instance
    try:
        instance.destroy()
    except tk.TclError:
        pass


def test_window_title(app):
    assert "E.I.S. Core" in app.title()


def test_sidebar_has_eight_sections(app):
    assert len(app._section_defs) == 8


@pytest.mark.parametrize("key", SECTIONS)
def test_section_opens(app, key: str):
    app.show_section(key)
    app.update()
    assert app._current == key


def test_theme_switch(app):
    from eis.core.settings import get_settings

    settings = get_settings()
    original = settings.get("appearance.mode")
    try:
        settings.set("appearance.mode", "light", save=False)
        app.refresh_theme()
        app.update()
        settings.set("appearance.mode", "dark", save=False)
        app.refresh_theme()
        app.update()
    finally:
        settings.set("appearance.mode", original, save=False)


def test_theme_palettes_complete():
    from eis.ui.theme import PALETTES

    required = {"bg", "bg_panel", "fg", "accent", "danger", "success"}
    for name, pal in PALETTES.items():
        assert required <= set(pal), f"palette {name} missing keys"


def test_status_bar_updates(app):
    app.set_status("hello world", badge="TEST")
    app.update()
    assert app.status_bar.message.get() == "hello world"
