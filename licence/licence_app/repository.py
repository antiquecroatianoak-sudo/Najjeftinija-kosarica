"""License persistence, scoped to one organization (tenant).

Every statement carries `organization_id = ?`, so one tenant can never read or
change another tenant's rows, even through a wrong id. Filtering is expressed
as a LicenseQuery and executed in SQL on indexed columns.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from .db import Database
from .models import BillingCycle, License, LicenseStatus


@dataclass(frozen=True)
class LicenseQuery:
    """Storage-independent filter. All conditions are combined with AND."""
    statuses: tuple[LicenseStatus, ...] = ()   # empty = any status
    category: str | None = None                # case-insensitive exact match
    text: str | None = None                    # case-insensitive substring of name or category
    started_on_or_before: date | None = None
    tracked: bool | None = None                # only licenses with/without usage_key
    ids: tuple[str, ...] = ()
    ordered: bool = True                       # False: caller sorts/aggregates itself -> planner may use any index


ALL = LicenseQuery()


class LicenseRepository(Protocol):
    def save(self, lic: License) -> None: ...
    def get(self, license_id: str) -> License | None: ...
    def find(self, query: LicenseQuery = ALL) -> list[License]: ...
    def update(self, lic: License) -> bool: ...
    def delete(self, license_id: str) -> bool: ...
    def categories(self) -> list[str]: ...


_COLUMNS = "id, name, category, cost, currency, billing_cycle, start_date, status, usage_key, auto_status"


class DuplicateUsageKey(ValueError):
    pass


class SQLiteLicenseRepository:
    def __init__(self, db: Database, organization_id: str):
        self.db = db
        self.org = organization_id

    # --- reads ------------------------------------------------------------
    def get(self, license_id: str) -> License | None:
        row = self.db.one(f"SELECT {_COLUMNS} FROM licenses WHERE organization_id = ? AND id = ?",
                          (self.org, license_id))
        return _row_to_license(row) if row else None

    def get_by_usage_key(self, key: str) -> License | None:
        row = self.db.one(f"SELECT {_COLUMNS} FROM licenses WHERE organization_id = ? AND usage_key = ?",
                          (self.org, key))
        return _row_to_license(row) if row else None

    def find(self, query: LicenseQuery = ALL) -> list[License]:
        sql, params = self.build_find_sql(query)
        return [_row_to_license(r) for r in self.db.query(sql, params)]

    def build_find_sql(self, query: LicenseQuery) -> tuple[str, list]:
        where, params = ["organization_id = ?"], [self.org]
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
        if query.tracked is not None:
            where.append("usage_key IS NOT NULL" if query.tracked else "usage_key IS NULL")
        if query.ids:
            where.append(f"id IN ({','.join('?' * len(query.ids))})")
            params += list(query.ids)
        sql = f"SELECT {_COLUMNS} FROM licenses WHERE {' AND '.join(where)}"
        return (sql + " ORDER BY name_key, id" if query.ordered else sql), params

    def explain(self, query: LicenseQuery) -> str:
        sql, params = self.build_find_sql(query)
        return "\n".join(r[-1] for r in self.db.query("EXPLAIN QUERY PLAN " + sql, params))

    def categories(self) -> list[str]:
        rows = self.db.query("SELECT min(category) FROM licenses WHERE organization_id = ?"
                             " GROUP BY category_key ORDER BY category_key", (self.org,))
        return [r[0] for r in rows]

    def tracking_since(self, license_id: str) -> str | None:
        return self.db.scalar("SELECT tracking_since FROM licenses WHERE organization_id = ? AND id = ?",
                              (self.org, license_id))

    # --- writes -------------------------------------------------------------
    def save(self, lic: License) -> None:
        try:
            self.db.execute(
                f"INSERT INTO licenses (organization_id, {_COLUMNS}, name_key, category_key, tracking_since)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? IS NULL THEN NULL ELSE datetime('now') END)",
                (self.org, *_license_to_row(lic), lic.usage_key),
            )
        except sqlite3.IntegrityError as e:
            # SQLite may report either constraint first; check the primary key explicitly
            if self.db.scalar("SELECT 1 FROM licenses WHERE id = ?", (lic.id,)):
                raise KeyError(lic.id) from e
            raise DuplicateUsageKey(lic.usage_key) from e

    def update(self, lic: License) -> bool:
        row = _license_to_row(lic)
        try:
            cur = self.db.execute(
                "UPDATE licenses SET name=?, category=?, cost=?, currency=?, billing_cycle=?, start_date=?,"
                " status=?, usage_key=?, auto_status=?, name_key=?, category_key=?,"
                " tracking_since = CASE WHEN ? IS NULL THEN NULL"
                "   WHEN usage_key IS ? THEN tracking_since ELSE datetime('now') END,"
                " updated_at=datetime('now') WHERE organization_id=? AND id=?",
                (*row[1:], lic.usage_key, lic.usage_key, self.org, row[0]),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateUsageKey(lic.usage_key) from e
        return cur.rowcount == 1

    def delete(self, license_id: str) -> bool:
        cur = self.db.execute("DELETE FROM licenses WHERE organization_id = ? AND id = ?", (self.org, license_id))
        return cur.rowcount == 1


def _license_to_row(lic: License) -> tuple:
    return (
        lic.id, lic.name, lic.category, str(lic.cost), lic.currency, lic.billing_cycle.value,
        lic.start_date.isoformat(), lic.status.value, lic.usage_key, int(lic.auto_status),
        lic.name.casefold(), lic.category.casefold(),
    )


def _row_to_license(row) -> License:
    return License(
        id=row["id"], name=row["name"], category=row["category"], cost=Decimal(row["cost"]),
        currency=row["currency"], billing_cycle=BillingCycle(row["billing_cycle"]),
        start_date=date.fromisoformat(row["start_date"]), status=LicenseStatus(row["status"]),
        usage_key=row["usage_key"], auto_status=bool(row["auto_status"]),
    )
