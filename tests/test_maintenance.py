"""Tests for maintenance safety gates and event log query shaping."""

from __future__ import annotations

from eis.modules.windows.maintenance import (
    clean,
    estimate_cleanable,
    network_reset_steps,
    perform_network_reset,
)
from eis.modules.windows.security import create_restore_point, start_defender_scan
from eis.modules.windows.services import change_service_state


class TestConfirmationGates:
    """Destructive helpers must refuse to act without explicit confirmation."""

    def test_clean_requires_confirmation(self, tmp_path):
        result = clean(["User temp folder"], confirm_executed=False)
        assert not result["ok"]
        assert "confirmation" in result["error"].lower()

    def test_network_reset_requires_confirmation(self):
        result = perform_network_reset(["winsock"], confirm_executed=False)
        assert not result["ok"]

    def test_service_change_requires_confirmation(self):
        result = change_service_state("Spooler", "stop", confirm_executed=False)
        assert not result["ok"]

    def test_restore_point_requires_confirmation(self):
        result = create_restore_point(confirm_executed=False)
        assert not result["ok"]

    def test_defender_scan_requires_confirmation(self):
        result = start_defender_scan("quick", confirm_executed=False)
        assert not result["ok"]


class TestNetworkResetCatalog:
    def test_steps_have_explanations(self):
        steps = network_reset_steps()
        assert steps
        for step in steps:
            assert step["command"]
            assert len(step["description"]) > 10

    def test_no_shutdown_like_commands(self):
        for step in network_reset_steps():
            assert "shutdown" not in step["command"].lower()
            assert "format" not in step["command"].lower()


class TestEstimate:
    def test_estimate_shape(self):
        result = estimate_cleanable()
        assert "total_bytes" in result
        assert result["total_bytes"] >= 0
        assert "total_human" in result


class TestEventQuery:
    def test_invalid_level_rejected(self):
        from eis.modules.windows.events import query_events

        result = query_events(level="bogus")
        assert not result["ok"]
        assert "Unknown level" in result["error"]

    def test_events_payload_shape(self):
        from eis.modules.windows.events import query_events

        result = query_events(level="error", max_events=5, days=30)
        assert "events" in result
        assert isinstance(result["events"], list)
