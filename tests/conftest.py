"""Shared pytest fixtures for the E.I.S. Core test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Temporary SQLite database path, fully migrated."""
    from eis.database.service import DatabaseService

    db_path = tmp_path / "test_eis.db"
    service = DatabaseService(db_path)
    service.initialize()
    return service.db_path


@pytest.fixture()
def db(tmp_db: Path):
    """A ready DatabaseService bound to a temporary database."""
    from eis.database.service import DatabaseService

    service = DatabaseService(tmp_db)
    service.initialize()
    yield service
    service.close()


@pytest.fixture()
def safety_engine():
    from eis.core.safety import SafetyEngine

    return SafetyEngine()


@pytest.fixture()
def sample_job(db):
    """One customer + device + job, returning the job id."""
    cid = db.customers.create(name="Test Customer", phone="555-0100", email="t@example.com")
    did = db.devices.create(customer_id=cid, brand="Dell", model="XPS 13", serial="SN-1")
    jid = db.jobs.create(device_id=did, title="No boot", problem="Dead, no LEDs")
    return jid
