"""Tests for privilege detection (non-elevating parts)."""

from __future__ import annotations

import os

from eis.core.privilege import current_user, is_admin, is_windows, require_elevation_hint


def test_is_admin_returns_bool():
    assert isinstance(is_admin(), bool)


def test_is_windows_matches_platform():
    assert is_windows() == (os.name == "nt")


def test_current_user_nonempty():
    assert current_user()


def test_require_elevation_hint_payload():
    payload = require_elevation_hint("SFC")
    assert payload["needs_elevation"]
    assert "SFC" in payload["error"]
    assert not payload["ok"]
