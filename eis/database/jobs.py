"""Job (repair ticket) and job-note repositories."""

from __future__ import annotations

from eis.database.repository import Repository

STATUSES = ("open", "diagnosing", "waiting_parts", "repairing", "done", "cancelled")
PRIORITIES = ("low", "normal", "high")
NOTE_KINDS = ("note", "diagnostic", "action", "result")


class JobRepository(Repository):
    table = "jobs"
    fields = ("device_id", "title", "status", "priority", "problem", "diagnosis", "solution", "cost", "finished_at")
    searchable = ("title", "problem", "diagnosis", "solution")

    def list_with_device(self, limit: int = 200, status: str = "") -> list[dict]:
        sql = (
            "SELECT j.*, d.model AS device_model, d.brand AS device_brand, "
            "c.name AS customer_name FROM jobs j "
            "LEFT JOIN devices d ON d.id = j.device_id "
            "LEFT JOIN customers c ON c.id = d.customer_id "
        )
        params: list = []
        if status:
            sql += "WHERE j.status = ? "
            params.append(status)
        sql += "ORDER BY j.id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def set_status(self, job_id: int, status: str) -> bool:
        if status not in STATUSES:
            return False
        finished = "datetime('now')" if status in ("done", "cancelled") else "NULL"
        cur = self._conn().execute(
            f"UPDATE jobs SET status = ?, finished_at = {finished}, "
            "updated_at = datetime('now') WHERE id = ?",
            (status, job_id),
        )
        self._conn().commit()
        return cur.rowcount > 0

    def status_counts(self) -> dict[str, int]:
        rows = self._conn().execute(
            "SELECT status, COUNT(*) AS c FROM jobs GROUP BY status"
        ).fetchall()
        return {r["status"]: r["c"] for r in rows}


class JobNoteRepository(Repository):
    table = "job_notes"
    fields = ("job_id", "body", "kind")
    searchable = ("body",)

    def list_for_job(self, job_id: int) -> list[dict]:
        return [
            dict(r)
            for r in self._conn().execute(
                "SELECT * FROM job_notes WHERE job_id = ? ORDER BY id ASC", (job_id,)
            ).fetchall()
        ]

    def add_note(self, job_id: int, body: str, kind: str = "note") -> int:
        if kind not in NOTE_KINDS:
            kind = "note"
        return self.create(job_id=job_id, body=body, kind=kind)
