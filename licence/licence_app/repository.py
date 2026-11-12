"""Storage layer. The service only knows the LicenseRepository protocol,
so SQLite can be swapped for Postgres (or a per-team store) without
touching business logic.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol

from .models import BillingCycle, License, LicenseStatus


class LicenseRepository(Protocol):
    def list(self) -> list[License]: ...
    def get(self, license_id: str) -> License | None: ...
    def add(self, lic: License) -> None: ...
    def update(self, lic: License) -> bool: ...
    def delete(self, license_id: str) -> bool: ...


class InMemoryLicenseRepository:
    """Used by tests and for quick demos."""

    def __init__(self, items: Iterable[License] = ()):
        self._items: dict[str, License] = {i.id: i for i in items}
        self._lock = threading.Lock()

    def list(self) -> list[License]:
        with self._lock:
            return list(self._items.values())

    def get(self, license_id: str) -> License | None:
        return self._items.get(license_id)

    def add(self, lic: License) -> None:
        with self._lock:
            if lic.id in self._items:
                raise KeyError(lic.id)
            self._items[lic.id] = lic

    def update(self, lic: License) -> bool:
        with self._lock:
            if lic.id not in self._items:
                return False
            self._items[lic.id] = lic
            return True

    def delete(self, license_id: str) -> bool:
        with self._lock:
            return self._items.pop(license_id, None) is not None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    cost          TEXT NOT NULL,      -- decimal stored as text: no float rounding
    currency      TEXT NOT NULL,
    billing_cycle TEXT NOT NULL,
    start_date    TEXT NOT NULL,      -- ISO date
    status        TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS licenses_status ON licenses(status);
"""

_COLUMNS = "id, name, category, cost, currency, billing_cycle, start_date, status"


class SQLiteLicenseRepository:
    def __init__(self, path: str = ":memory:"):
        # One shared connection guarded by a lock: simple and safe for the
        # threaded stdlib server at small-team scale.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def list(self) -> list[License]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM licenses ORDER BY created_at, name"
            ).fetchall()
        return [_row_to_license(r) for r in rows]

    def get(self, license_id: str) -> License | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM licenses WHERE id = ?", (license_id,)
            ).fetchone()
        return _row_to_license(row) if row else None

    def add(self, lic: License) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT INTO licenses ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                _license_to_row(lic),
            )

    def update(self, lic: License) -> bool:
        row = _license_to_row(lic)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE licenses SET name=?, category=?, cost=?, currency=?, billing_cycle=?,"
                " start_date=?, status=?, updated_at=datetime('now') WHERE id=?",
                (*row[1:], row[0]),
            )
        return cur.rowcount == 1

    def delete(self, license_id: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
        return cur.rowcount == 1


def _license_to_row(lic: License) -> tuple[str, ...]:
    return (
        lic.id, lic.name, lic.category, str(lic.cost), lic.currency,
        lic.billing_cycle.value, lic.start_date.isoformat(), lic.status.value,
    )


def _row_to_license(row: tuple) -> License:
    id_, name, category, cost, currency, cycle, start, status = row
    return License(
        id=id_, name=name, category=category, cost=Decimal(cost), currency=currency,
        billing_cycle=BillingCycle(cycle), start_date=date.fromisoformat(start),
        status=LicenseStatus(status),
    )
