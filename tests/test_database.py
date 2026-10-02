"""Tests for the SQLite database layer."""

from __future__ import annotations

import pytest

from eis.database.jobs import STATUSES
from eis.database.service import DatabaseService


class TestCustomers:
    def test_create_and_get(self, db: DatabaseService):
        cid = db.customers.create(name="Jane Doe", phone="555-0100")
        customer = db.customers.get(cid)
        assert customer["name"] == "Jane Doe"
        assert customer["phone"] == "555-0100"

    def test_search(self, db: DatabaseService):
        db.customers.create(name="Alpha", phone="111")
        db.customers.create(name="Beta", phone="222")
        results = db.customers.search("beta")
        assert len(results) == 1
        assert results[0]["name"] == "Beta"

    def test_update(self, db: DatabaseService):
        cid = db.customers.create(name="Old Name")
        db.customers.update(cid, name="New Name")
        assert db.customers.get(cid)["name"] == "New Name"

    def test_delete(self, db: DatabaseService):
        cid = db.customers.create(name="Doomed")
        assert db.customers.delete(cid)
        assert db.customers.get(cid) is None


class TestDevices:
    def test_device_with_customer_join(self, db: DatabaseService):
        cid = db.customers.create(name="Owner")
        did = db.devices.create(customer_id=cid, brand="HP", model="EliteBook")
        rows = db.devices.list_with_customer()
        assert any(r["id"] == did and r["customer_name"] == "Owner" for r in rows)

    def test_cascade_delete(self, db: DatabaseService):
        cid = db.customers.create(name="Owner")
        did = db.devices.create(customer_id=cid)
        db.jobs.create(device_id=did, title="Job")
        db.customers.delete(cid)
        assert db.devices.get(did) is None
        assert db.jobs.count() == 0


class TestJobs:
    def test_create_defaults(self, db: DatabaseService, sample_job: int):
        job = db.jobs.get(sample_job)
        assert job["status"] == "open"
        assert job["priority"] == "normal"

    def test_set_status_done_sets_finished(self, db: DatabaseService, sample_job: int):
        assert db.jobs.set_status(sample_job, "done")
        job = db.jobs.get(sample_job)
        assert job["status"] == "done"
        assert job["finished_at"]

    def test_invalid_status_rejected(self, db: DatabaseService, sample_job: int):
        assert not db.jobs.set_status(sample_job, "exploded")
        assert set(STATUSES) >= {"open", "done"}

    def test_status_counts(self, db: DatabaseService, sample_job: int):
        counts = db.jobs.status_counts()
        assert counts.get("open") == 1

    def test_notes(self, db: DatabaseService, sample_job: int):
        db.job_notes.add_note(sample_job, "Diagnosed PSU", kind="diagnostic")
        notes = db.job_notes.list_for_job(sample_job)
        assert len(notes) == 1
        assert notes[0]["kind"] == "diagnostic"
        # invalid kind is coerced
        db.job_notes.add_note(sample_job, "x", kind="bogus")
        assert db.job_notes.list_for_job(sample_job)[1]["kind"] == "note"


class TestCommandHistoryRepository:
    def test_add_and_recent(self, db: DatabaseService):
        db.command_history.add_entry("test.action", "cmd", result="ok")
        rows = db.command_history.recent()
        assert rows[0]["action"] == "test.action"
        assert rows[0]["details"] == {}

    def test_purge(self, db: DatabaseService):
        old_id = db.command_history.add_entry("old.entry")
        recent_id = db.command_history.add_entry("new.entry")
        # Backdate one row so it is genuinely older than the cutoff
        # (created_at has second precision, so a row inserted in the same
        # second as the purge is never strictly older than 'now').
        conn = db.command_history._conn()
        conn.execute(
            "UPDATE command_history SET created_at = datetime('now', '-30 days') WHERE id = ?",
            (old_id,),
        )
        conn.commit()
        removed = db.command_history.purge_older_than_days(7)
        assert removed == 1
        remaining = db.command_history.recent()
        assert [r["id"] for r in remaining] == [recent_id]


class TestKBFeedback:
    def test_rate_and_ratio(self, db: DatabaseService):
        repo = db.kb_feedback
        repo.rate("kb-1", True)
        repo.rate("kb-1", True)
        repo.rate("kb-1", False)
        assert repo.helpful_ratio("kb-1") == pytest.approx(2 / 3)

    def test_ratio_none_when_unrated(self, db: DatabaseService):
        assert db.kb_feedback.helpful_ratio("kb-unknown") is None


class TestSchemaAndBackup:
    def test_migrations_idempotent(self, db: DatabaseService, tmp_db):
        from eis.database.schema import apply_migrations

        assert apply_migrations(tmp_db) == 1  # still version 1, no errors

    def test_backup_creates_file(self, db: DatabaseService, tmp_path):
        dest = db.backup(dest_dir=tmp_path)
        assert dest.exists()
        assert dest.stat().st_size > 0

    def test_info_counts(self, db: DatabaseService):
        info = db.info()
        assert info["version"] == 1
        assert info["counts"]["customers"] == 0
