"""Schema management + migrations for the E.I.S. Core database."""

from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path

from eis.database.connection import get_connection

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _migration_files() -> list[tuple[int, str]]:
    """Return (version, filename) sorted by version."""
    items: list[tuple[int, str]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        try:
            version = int(path.name.split("_", 1)[0])
        except (ValueError, IndexError):
            log.warning("Skipping malformed migration name: %s", path.name)
            continue
        items.append((version, path.name))
    return sorted(items)


def current_version(conn) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations"
    ).fetchone()
    return int(row["v"]) if row else 0


def apply_migrations(db_path: Path | str | None = None) -> int:
    """Apply pending migrations; returns the new schema version."""
    conn = get_connection(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()

    applied = 0
    for version, name in _migration_files():
        if version <= current_version(conn):
            continue
        sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
        log.info("Applying migration %s", name)
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)", (version, name))
        conn.commit()
        applied += 1
    if applied:
        log.info("Database migrated to version %d", current_version(conn))
    return current_version(conn)


def database_info(db_path: Path | str | None = None) -> dict:
    """Small status payload for Settings → Database."""
    conn = get_connection(db_path)
    tables = [
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    counts = {}
    for t in tables:
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        except Exception:  # pragma: no cover
            counts[t] = -1
    return {
        "version": current_version(conn),
        "tables": tables,
        "counts": counts,
    }
