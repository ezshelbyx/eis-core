"""Customer and device repositories."""

from __future__ import annotations

from eis.database.repository import Repository


class CustomerRepository(Repository):
    table = "customers"
    fields = ("name", "phone", "email", "notes")
    searchable = ("name", "phone", "email")


class DeviceRepository(Repository):
    table = "devices"
    fields = ("customer_id", "device_type", "brand", "model", "serial", "os", "specs", "password_notes", "notes")
    searchable = ("brand", "model", "serial", "os", "notes")

    def list_for_customer(self, customer_id: int) -> list[dict]:
        return self.list(order_by="id")

    def list_with_customer(self, limit: int = 200) -> list[dict]:
        """Devices joined with their customer name (for UI lists)."""
        sql = (
            "SELECT d.*, c.name AS customer_name FROM devices d "
            "LEFT JOIN customers c ON c.id = d.customer_id "
            "ORDER BY d.id DESC LIMIT ?"
        )
        rows = self._conn().execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]
