"""Database service facade - one object wiring all repositories together.

Usage::

    from eis.database.service import get_db
    db = get_db()
    cid = db.customers.create(name="Jane Doe", phone="555-0100")
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from eis.core.logging_config import DB_PATH
from eis.core.paths import record_command
from eis.database.customers import CustomerRepository, DeviceRepository
from eis.database.history import CommandHistoryRepository, KnowledgeFeedbackRepository
from eis.database.jobs import JobNoteRepository, JobRepository
from eis.database.schema import apply_migrations, current_version
from eis.database.connection import close_connection, get_connection

log = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.customers = CustomerRepository(self.db_path)
        self.devices = DeviceRepository(self.db_path)
        self.jobs = JobRepository(self.db_path)
        self.job_notes = JobNoteRepository(self.db_path)
        self.command_history = CommandHistoryRepository(self.db_path)
        self.kb_feedback = KnowledgeFeedbackRepository(self.db_path)
        self._migrated = False

    # ------------------------------------------------------------------
    def initialize(self) -> int:
        """Create/migrate the schema (idempotent)."""
        version = apply_migrations(self.db_path)
        self._migrated = True
        log.info("Database ready at %s (schema v%d)", self.db_path, version)
        return version

    def ensure_ready(self) -> None:
        if not self._migrated:
            self.initialize()

    def info(self) -> dict:
        self.ensure_ready()
        from eis.database.schema import database_info
        return database_info(self.db_path)

    def backup(self, dest_dir=None) -> Path:
        """Copy the SQLite file (WAL-safe via sqlite backup API)."""
        import sqlite3
        from eis.core.logging_config import BACKUP_DIR, ensure_runtime_dirs

        self.ensure_ready()
        ensure_runtime_dirs()
        dest_dir = Path(dest_dir) if dest_dir else BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"eis_backup_{stamp}.db"
        src = sqlite3.connect(str(self.db_path))
        dst = sqlite3.connect(str(dest))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        record_command("database.backup", command=str(dest), result="ok")
        return dest

    def close(self) -> None:
        close_connection()


_service: DatabaseService | None = None
_lock = threading.Lock()


def get_db(db_path: Path | str | None = None) -> DatabaseService:
    """Process-wide DatabaseService singleton."""
    global _service
    with _lock:
        if _service is None:
            _service = DatabaseService(db_path)
            _service.initialize()
        return _service
