"""Tiny generic repository base for E.I.S. Core SQLite tables."""

from __future__ import annotations

import sqlite3
from typing import Any

from eis.database.connection import get_connection


class Repository:
    """CRUD helper bound to one table.

    Subclasses declare ``table`` and ``fields``.  All methods accept an
    optional ``db_path`` so tests can point at a temporary database.
    """

    table: str = ""
    fields: tuple[str, ...] = ()
    searchable: tuple[str, ...] = ()

    def __init__(self, db_path: Any = None):
        self.db_path = db_path

    # -- helpers -----------------------------------------------------------
    def _conn(self):
        return get_connection(self.db_path)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row is not None else None

    # -- CRUD --------------------------------------------------------------
    def create(self, **values) -> int:
        cols = [f for f in self.fields if f in values]
        vals = [values[c] for c in cols]
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})"
        cur = self._conn().execute(sql, vals)
        self._conn().commit()
        return int(cur.lastrowid or 0)

    def get(self, item_id: int) -> dict | None:
        row = self._conn().execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (item_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def list(self, order_by: str = "", limit: int = 0) -> list[dict]:
        sql = f"SELECT * FROM {self.table}"
        if order_by:
            if order_by.lstrip("-").split(" ")[0] not in self.fields + ("id",):
                order_by = "id"
        else:
            order_by = "id"
        direction = "DESC" if order_by.startswith("-") else "ASC"
        col = order_by.lstrip("-").split(" ")[0]
        sql += f" ORDER BY {col} {direction}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn().execute(sql).fetchall()]

    def update(self, item_id: int, **values) -> bool:
        cols = [f for f in self.fields if f in values]
        if not cols:
            return False
        set_sql = ", ".join(f"{c} = ?" for c in cols)
        vals = [values[c] for c in cols] + [item_id]
        cur = self._conn().execute(
            f"UPDATE {self.table} SET {set_sql} WHERE id = ?", vals
        )
        self._conn().commit()
        return cur.rowcount > 0

    def delete(self, item_id: int) -> bool:
        cur = self._conn().execute(f"DELETE FROM {self.table} WHERE id = ?", (item_id,))
        self._conn().commit()
        return cur.rowcount > 0

    def count(self) -> int:
        row = self._conn().execute(f"SELECT COUNT(*) AS c FROM {self.table}").fetchone()
        return int(row["c"])

    def search(self, term: str, limit: int = 50) -> list[dict]:
        """Case-insensitive substring search over ``searchable`` columns."""
        if not term or not self.searchable:
            return self.list(limit=limit)
        like = f"%{term.strip().lower()}%"
        clauses = " OR ".join(f"LOWER({c}) LIKE ?" for c in self.searchable)
        sql = f"SELECT * FROM {self.table} WHERE {clauses} ORDER BY id DESC LIMIT ?"
        rows = self._conn().execute(sql, (*[like] * len(self.searchable), limit)).fetchall()
        return [dict(r) for r in rows]
