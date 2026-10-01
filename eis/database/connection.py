"""SQLite connection management for E.I.S. Core.

A single connection per thread (SQLite default) with WAL journaling enabled
for good read concurrency on low-end machines.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from eis.core.logging_config import DB_PATH, ensure_runtime_dirs

log = logging.getLogger(__name__)

_local = threading.local()


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return this thread's connection, creating it when needed."""
    path = Path(db_path) if db_path else DB_PATH
    conn = getattr(_local, "conn", None)
    if conn is not None:
        # Same file?  (Tests use temporary DBs.)
        if getattr(_local, "conn_path", None) == str(path):
            return conn
        try:
            conn.close()
        except Exception:  # pragma: no cover
            pass
        _local.conn = None
    ensure_runtime_dirs()
    conn = _configure(sqlite3.connect(str(path), timeout=15))
    _local.conn = conn
    _local.conn_path = str(path)
    log.debug("Opened SQLite connection: %s", path)
    return conn


def close_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:  # pragma: no cover
            pass
        _local.conn = None
        _local.conn_path = None


def query(db_path: Path | str | None, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Run a SELECT and return all rows."""
    conn = get_connection(db_path)
    return conn.execute(sql, params).fetchall()


def execute(db_path: Path | str | None, sql: str, params: tuple = ()) -> int:
    """Run a write statement and commit; returns lastrowid."""
    conn = get_connection(db_path)
    cur = conn.execute(sql, params)
    conn.commit()
    return int(cur.lastrowid or 0)


def executescript(db_path: Path | str | None, script: str) -> None:
    conn = get_connection(db_path)
    conn.executescript(script)
    conn.commit()
