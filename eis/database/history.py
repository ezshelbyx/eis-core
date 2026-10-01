"""Repositories for command history and KB feedback."""

from __future__ import annotations

import json

from eis.database.repository import Repository


class CommandHistoryRepository(Repository):
    table = "command_history"
    fields = ("action", "command", "result", "error", "details")
    searchable = ("action", "command", "error")

    def add_entry(self, action: str, command: str = "", result: str = "ok",
                  error: str = "", details: dict | None = None) -> int:
        return self.create(
            action=action,
            command=command,
            result=result,
            error=error,
            details=json.dumps(details or {}, ensure_ascii=False),
        )

    def recent(self, limit: int = 200) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM command_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.get("details") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
            out.append(d)
        return out

    def purge_older_than_days(self, days: int) -> int:
        cur = self._conn().execute(
            "DELETE FROM command_history WHERE created_at < datetime('now', ?)",
            (f"-{int(days)} days",),
        )
        self._conn().commit()
        return cur.rowcount


class KnowledgeFeedbackRepository(Repository):
    table = "kb_feedback"
    fields = ("kb_id", "helpful", "note")
    searchable = ("kb_id", "note")

    def rate(self, kb_id: str, helpful: bool, note: str = "") -> int:
        return self.create(kb_id=kb_id, helpful=1 if helpful else 0, note=note)

    def helpful_ratio(self, kb_id: str) -> float | None:
        row = self._conn().execute(
            "SELECT AVG(helpful) AS avg FROM kb_feedback WHERE kb_id = ?", (kb_id,)
        ).fetchone()
        if row is None or row["avg"] is None:
            return None
        return float(row["avg"])
