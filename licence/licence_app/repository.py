"""Persistence layer.

The service depends only on the LicenseRepository protocol. Filtering is
expressed as a LicenseQuery and executed by the repository itself (SQL WHERE
on indexed columns for SQLite), so the service never loads rows it does not
need.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol

from .models import BillingCycle, License, LicenseStatus


@dataclass(frozen=True)
class LicenseQuery:
    """Storage-independent filter. All conditions are combined with AND."""
    statuses: tuple[LicenseStatus, ...] = ()   # empty = any status
    category: str | None = None                # case-insensitive exact match
    text: str | None = None                    # case-insensitive substring of name or category
    started_on_or_before: date | None = None   # only licenses already started by this date

    def matches(self, lic: License) -> bool:
        if self.statuses and lic.status not in self.statuses:
            return False
        if self.category and lic.category.casefold() != self.category.casefold():
            return False
        if self.text and self.text.casefold() not in f"{lic.name}\n{lic.category}".casefold():
            return False
        if self.started_on_or_before and lic.start_date > self.started_on_or_before:
            return False
        return True


ALL = LicenseQuery()


class LicenseRepository(Protocol):
    def save(self, lic: License) -> None:
        """Insert a new license. Raises KeyError if the id already exists."""
    def get(self, license_id: str) -> License | None: ...
    def find(self, query: LicenseQuery = ALL) -> list[License]:
        """Matching licenses ordered by name (case-insensitive), then id."""
    def update(self, lic: License) -> bool:
        """Replace an existing license. False if it does not exist."""
    def delete(self, license_id: str) -> bool:
        """False if it did not exist."""
    def categories(self) -> list[str]: ...


def _sort_key(lic: License) -> tuple[str, str]:
    return (lic.name.casefold(), lic.id)  # same order as SQLite: name_key, id


class InMemoryLicenseRepository:
    """Reference implementation used by unit tests and demos."""

    def __init__(self, items: Iterable[License] = ()):
        self._items: dict[str, License] = {i.id: i for i in items}
        self._lock = threading.Lock()

    def save(self, lic: License) -> None:
        with self._lock:
            if lic.id in self._items:
                raise KeyError(lic.id)
            self._items[lic.id] = lic

    def get(self, license_id: str) -> License | None:
        return self._items.get(license_id)

    def find(self, query: LicenseQuery = ALL) -> list[License]:
        with self._lock:
            items = [l for l in self._items.values() if query.matches(l)]
        return sorted(items, key=_sort_key)

    def update(self, lic: License) -> bool:
        with self._lock:
            if lic.id not in self._items:
                return False
            self._items[lic.id] = lic
            return True

    def delete(self, license_id: str) -> bool:
        with self._lock:
            return self._items.pop(license_id, None) is not None

    def categories(self) -> list[str]:
        first: dict[str, str] = {}
        for lic in sorted(self.find(), key=lambda l: l.category):
            first.setdefault(lic.category.casefold(), lic.category)
        return [first[k] for k in sorted(first)]

    def close(self) -> None:
        pass


SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    cost          TEXT NOT NULL,   -- exact decimal as text (no float rounding)
    currency      TEXT NOT NULL CHECK (length(currency) = 3),
    billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('monthly','quarterly','yearly')),
    start_date    TEXT NOT NULL,   -- ISO date: sorts and compares correctly as text
    status        TEXT NOT NULL CHECK (status IN ('active','inactive','cancelled')),
    name_key      TEXT NOT NULL,   -- casefold(name): Unicode-aware (č/Č), unlike SQLite lower()/NOCASE
    category_key  TEXT NOT NULL,   -- casefold(category)
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
) WITHOUT ROWID;
-- Dashboard / filter paths: status (+ start_date), category, and the default ORDER BY.
CREATE INDEX IF NOT EXISTS licenses_status_start ON licenses(status, start_date);
CREATE INDEX IF NOT EXISTS licenses_category ON licenses(category_key);
CREATE INDEX IF NOT EXISTS licenses_name ON licenses(name_key, id);
"""

_COLUMNS = "id, name, category, cost, currency, billing_cycle, start_date, status"
_WRITE_COLUMNS = _COLUMNS + ", name_key, category_key"


class SQLiteLicenseRepository:
    """SQLite store. One connection guarded by a lock: safe for the threaded
    stdlib server and plenty for a small team (WAL keeps reads cheap)."""

    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        with self._lock:
            c = self._conn
            if path != ":memory:":
                c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA busy_timeout=5000")
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Baza ima noviju shemu ({version}) od aplikacije ({SCHEMA_VERSION}).")
            c.execute("BEGIN")
            try:
                _migrate_from_v0(c)
                for statement in _SCHEMA.split(";"):  # not executescript: it would COMMIT early
                    if statement.strip():
                        c.execute(statement)
                c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA optimize")
            self._conn.close()

    # --- reads ------------------------------------------------------------
    def get(self, license_id: str) -> License | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM licenses WHERE id = ?", (license_id,)
            ).fetchone()
        return _row_to_license(row) if row else None

    def find(self, query: LicenseQuery = ALL) -> list[License]:
        sql, params = self.build_find_sql(query)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_license(r) for r in rows]

    @staticmethod
    def build_find_sql(query: LicenseQuery) -> tuple[str, list]:
        where, params = [], []
        if query.statuses:
            where.append(f"status IN ({','.join('?' * len(query.statuses))})")
            params += [s.value for s in query.statuses]
        if query.started_on_or_before:
            where.append("start_date <= ?")
            params.append(query.started_on_or_before.isoformat())
        if query.category:
            where.append("category_key = ?")
            params.append(query.category.casefold())
        if query.text:
            # instr instead of LIKE: no wildcard escaping issues with % or _
            where.append("(instr(name_key, ?) > 0 OR instr(category_key, ?) > 0)")
            params += [query.text.casefold()] * 2
        sql = f"SELECT {_COLUMNS} FROM licenses"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return sql + " ORDER BY name_key, id", params

    def categories(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT min(category) FROM licenses GROUP BY category_key ORDER BY category_key"
            ).fetchall()
        return [cat for (cat,) in rows]

    def explain(self, query: LicenseQuery) -> str:
        """Query plan text (diagnostics and tests)."""
        sql, params = self.build_find_sql(query)
        with self._lock:
            rows = self._conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        return "\n".join(r[-1] for r in rows)

    # --- writes -----------------------------------------------------------
    def save(self, lic: License) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    f"INSERT INTO licenses ({_WRITE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _license_to_row(lic),
                )
        except sqlite3.IntegrityError as e:
            raise KeyError(lic.id) from e

    def update(self, lic: License) -> bool:
        row = _license_to_row(lic)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE licenses SET name=?, category=?, cost=?, currency=?, billing_cycle=?,"
                " start_date=?, status=?, name_key=?, category_key=?, updated_at=datetime('now')"
                " WHERE id=?",
                (*row[1:], row[0]),
            )
        return cur.rowcount == 1

    def delete(self, license_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
        return cur.rowcount == 1


def _migrate_from_v0(conn: sqlite3.Connection) -> None:
    """Version 0.1.0 had no *_key columns: add and backfill them."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(licenses)")}
    if not cols or "name_key" in cols:
        return
    conn.execute("ALTER TABLE licenses ADD COLUMN name_key TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE licenses ADD COLUMN category_key TEXT NOT NULL DEFAULT ''")
    rows = conn.execute("SELECT id, name, category FROM licenses").fetchall()
    conn.executemany(
        "UPDATE licenses SET name_key = ?, category_key = ? WHERE id = ?",
        [(name.casefold(), cat.casefold(), id_) for id_, name, cat in rows],
    )
    conn.execute("DROP INDEX IF EXISTS licenses_status")


def _license_to_row(lic: License) -> tuple[str, ...]:
    return (
        lic.id, lic.name, lic.category, str(lic.cost), lic.currency,
        lic.billing_cycle.value, lic.start_date.isoformat(), lic.status.value,
        lic.name.casefold(), lic.category.casefold(),
    )


def _row_to_license(row: tuple) -> License:
    id_, name, category, cost, currency, cycle, start, status = row
    return License(
        id=id_, name=name, category=category, cost=Decimal(cost), currency=currency,
        billing_cycle=BillingCycle(cycle), start_date=date.fromisoformat(start),
        status=LicenseStatus(status),
    )
