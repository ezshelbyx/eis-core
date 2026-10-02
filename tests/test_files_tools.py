"""Tests for file tools: hashing, duplicates, metadata, generators."""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path

import pytest

from eis.modules.files.duplicates import find_duplicates
from eis.modules.files.generators import (
    generate_passphrase,
    generate_password,
    url_payload,
    vcard_payload,
    wifi_payload,
)
from eis.modules.files.hashing import hash_file, hash_text, verify_file
from eis.modules.files.metadata import inspect
from eis.modules.files.wordlist import WORDS


class TestHashing:
    def test_known_digest(self, tmp_path: Path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"hello world")
        result = hash_file(f, ("sha256",))
        assert result["ok"]
        assert result["hashes"]["sha256"] == hashlib.sha256(b"hello world").hexdigest()

    def test_all_algorithms(self, tmp_path: Path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"data")
        result = hash_file(f, ("md5", "sha1", "sha256", "sha512"))
        assert set(result["hashes"]) == {"md5", "sha1", "sha256", "sha512"}

    def test_unsupported_algorithm(self, tmp_path: Path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"data")
        assert not hash_file(f, ("crc99",))["ok"]

    def test_verify_match_and_mismatch(self, tmp_path: Path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"payload")
        good = verify_file(f, hashlib.sha256(b"payload").hexdigest())
        assert good["match"]
        bad = verify_file(f, "0" * 64)
        assert not bad["match"]

    def test_hash_text(self):
        assert hash_text("abc")["hash"] == hashlib.sha256(b"abc").hexdigest()


class _AllowScanRoots:
    """Stand-in safety engine that permits scanning pytest tmp dirs.

    Real tmp_path resolves inside the user profile (AppData\\...), which the
    safety engine correctly refuses to scan; the guard itself is covered by
    test_protected_root_blocked using the real engine.
    """

    def guard_scan_root(self, root):
        return True, ""


@pytest.fixture()
def allow_scan_roots(monkeypatch):
    monkeypatch.setattr(
        "eis.modules.files.duplicates.get_safety_engine", lambda: _AllowScanRoots()
    )


class TestDuplicates:
    def test_finds_duplicates(self, tmp_path: Path, allow_scan_roots):
        d1 = tmp_path / "one"
        d2 = tmp_path / "two"
        d1.mkdir()
        d2.mkdir()
        content = secrets.token_bytes(8192)  # above min_size
        (d1 / "f.bin").write_bytes(content)
        (d2 / "g.bin").write_bytes(content)
        result = find_duplicates([tmp_path])
        assert result["duplicate_groups"] == 1
        assert result["wasted_bytes"] == 8192

    def test_ignores_unique_files(self, tmp_path: Path, allow_scan_roots):
        (tmp_path / "x.bin").write_bytes(b"A" * 5000)
        (tmp_path / "y.bin").write_bytes(b"B" * 5000)
        result = find_duplicates([tmp_path])
        assert result["duplicate_groups"] == 0

    def test_protected_root_blocked(self):
        result = find_duplicates(["C:/Windows/System32"])
        assert result["blocked_roots"], "System32 must be refused"
        assert result["scanned_files"] == 0

    def test_delete_mode_requires_confirmation(self, tmp_path: Path, allow_scan_roots):
        d = tmp_path / "d"
        d.mkdir()
        content = secrets.token_bytes(8192)
        (d / "a.bin").write_bytes(content)
        (d / "b.bin").write_bytes(content)
        result = find_duplicates([tmp_path], delete_mode="keep_first", confirm_delete=False)
        assert (d / "b.bin").exists()  # nothing deleted without confirmation


class TestMetadata:
    def test_file_metadata(self, tmp_path: Path):
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x" * 1234)
        meta = inspect(f)
        assert meta["ok"]
        assert meta["size_bytes"] == 1234
        assert meta["extension"] == ".txt"
        assert meta["modified"]

    def test_missing_path(self, tmp_path: Path):
        assert not inspect(tmp_path / "nope")["ok"]


class TestGenerators:
    def test_password_length_and_charset(self):
        result = generate_password(length=24, use_symbols=False)
        pw = result["password"]
        assert len(pw) == 24
        assert not any(c in "!@#$%^&*()" for c in pw)

    def test_password_entropy_reported(self):
        result = generate_password(length=32)
        assert result["entropy_bits"] > 80

    def test_password_all_sets_disabled_rejected(self):
        assert not generate_password(use_lower=False, use_upper=False,
                                     use_digits=False, use_symbols=False)["ok"]

    def test_passwords_unique(self):
        pws = {generate_password(length=16)["password"] for _ in range(20)}
        assert len(pws) == 20

    def test_passphrase_words(self):
        result = generate_passphrase(words=5)
        assert result["ok"]
        assert len(result["passphrase"].split("-")) == 6  # 5 words + digit suffix

    def test_wordlist_size(self):
        assert len(WORDS) >= 300

    def test_wifi_payload_escapes(self):
        payload = wifi_payload("My;Net", "pass:word,x")
        assert "\\;" in payload and "\\:" in payload

    def test_url_payload_adds_scheme(self):
        assert url_payload("example.com").startswith("https://")

    def test_vcard_payload(self):
        card = vcard_payload("Tech", org="EIS", phone="555")
        assert card.startswith("BEGIN:VCARD")
        assert "FN:Tech" in card
