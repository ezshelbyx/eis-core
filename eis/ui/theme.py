"""Theme engine: dark/light palettes and a font scale for the dashboard."""

from __future__ import annotations

from eis.core.settings import get_settings

PALETTES = {
    "eis-dark": {
        "bg": "#1b1f24",
        "bg_panel": "#232830",
        "bg_input": "#2b323b",
        "bg_hover": "#323a45",
        "fg": "#e6e9ee",
        "fg_dim": "#9aa4b1",
        "accent": "#0f6cbd",
        "accent_fg": "#ffffff",
        "success": "#3fb950",
        "warning": "#d29922",
        "danger": "#f85149",
        "border": "#3d444d",
        "select": "#0f6cbd",
    },
    "eis-light": {
        "bg": "#f4f6f8",
        "bg_panel": "#ffffff",
        "bg_input": "#eef1f4",
        "bg_hover": "#e2e8ee",
        "fg": "#1c2733",
        "fg_dim": "#5a6572",
        "accent": "#0f6cbd",
        "accent_fg": "#ffffff",
        "success": "#1a7f37",
        "warning": "#9a6700",
        "danger": "#cf222e",
        "border": "#d5dbe1",
        "select": "#0f6cbd",
    },
}

DARK = "eis-dark"
LIGHT = "eis-light"


def palette() -> dict:
    """Active palette dict."""
    settings = get_settings()
    mode = settings.get("appearance.mode", "system")
    theme = settings.get("appearance.theme", DARK)
    if mode == "dark":
        return PALETTES[DARK]
    if mode == "light":
        return PALETTES[LIGHT]
    # 'system': prefer dark by default (technician tool look), but honor theme
    return PALETTES.get(theme, PALETTES[DARK])


def is_dark() -> bool:
    return palette()["bg"] == PALETTES[DARK]["bg"]


def font_size() -> int:
    try:
        return max(8, min(16, int(get_settings().get("appearance.font_size", 10))))
    except (TypeError, ValueError):
        return 10
