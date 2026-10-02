"""Tests for the troubleshooting knowledge base."""

from __future__ import annotations

import json
from pathlib import Path

from eis.modules.knowledge import kb
from eis.modules.knowledge.kb_data import ENTRIES


class TestSearch:
    def test_all_entries_available(self):
        entries = kb.all_entries()
        assert len(entries) >= len(ENTRIES)
        assert all("id" in e and "solutions" in e for e in entries)

    def test_search_ranks_error_patterns(self):
        hits = kb.search("0x800f0922")
        assert hits
        assert hits[0]["id"] == "kb-0009-corrupt-system"

    def test_search_symptom_words(self):
        hits = kb.search("no internet connected")
        assert hits[0]["id"] == "kb-0003-no-internet"

    def test_empty_query_returns_all(self):
        assert len(kb.search("")) >= len(ENTRIES)

    def test_category_filter(self):
        hits = kb.search("", category="Network")
        assert hits
        assert all(h["category"] == "Network" for h in hits)


class TestErrorMatching:
    def test_match_error_text(self):
        hits = kb.match_error_text("update failed with 0x80073712 and CBS corruption")
        assert hits
        assert any(h["id"] == "kb-0009-corrupt-system" for h in hits)

    def test_no_match(self):
        assert kb.match_error_text("nothing relevant here at all") == []


class TestCustomEntries:
    def test_add_and_delete_roundtrip(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(kb, "KB_CUSTOM_PATH", tmp_path / "kb_custom.json")
        entry = kb.add_custom_entry(
            "Test issue", "General", ["symptom one"], ["cause one"],
            ["check one"], ["fix one"], error_patterns=["ERR_TEST_42"],
        )
        assert entry["custom"] is True
        stored = json.loads((tmp_path / "kb_custom.json").read_text(encoding="utf-8"))
        assert stored[0]["title"] == "Test issue"
        assert kb.delete_custom_entry(entry["id"])
        assert kb.all_entries() == list(ENTRIES)

    def test_get_entry(self):
        assert kb.get_entry("kb-0003-no-internet")["category"] == "Network"
        assert kb.get_entry("does-not-exist") is None

    def test_export_markdown(self, tmp_path: Path):
        target = tmp_path / "kb.md"
        result = kb.export_entries(target, "md")
        assert result["ok"]
        assert "# E.I.S. Core" in target.read_text(encoding="utf-8")

    def test_custom_entry_matches_error_text(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(kb, "KB_CUSTOM_PATH", tmp_path / "kb_custom.json")
        kb.add_custom_entry("Custom", "General", [], [], [], [], error_patterns=["UNIQUE_ERR_XYZ"])
        hits = kb.match_error_text("saw UNIQUE_ERR_XYZ in logs")
        assert any(h["title"] == "Custom" for h in hits)
