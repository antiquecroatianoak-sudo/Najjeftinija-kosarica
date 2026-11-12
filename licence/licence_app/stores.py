"""Persistence for everything except licenses (see repository.py).

Thin SQL wrappers grouped by aggregate; business rules live in services.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from .db import Database
from .models import Organization


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --- organizations & users ----------------------------------------------------

def _org(row) -> Organization:
    return Organization(id=row["id"], name=row["name"], slug=row["slug"],
                        reference_currency=row["reference_currency"], accent=row["accent"],
                        inactivity_days=row["inactivity_days"], notify_days=row["notify_days"])


class OrganizationStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, name: str, slug: str, **fields: Any) -> Organization:
        org_id = new_id("org")
        cols = ["id", "name", "slug", *fields]
        self.db.execute(f"INSERT INTO organizations ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        (org_id, name, slug, *fields.values()))
        return self.get(org_id)

    def get(self, org_id: str) -> Organization | None:
        row = self.db.one("SELECT * FROM organizations WHERE id = ?", (org_id,))
        return _org(row) if row else None

    def by_slug(self, slug: str) -> Organization | None:
        row = self.db.one("SELECT * FROM organizations WHERE slug = ?", (slug,))
        return _org(row) if row else None

    def all(self) -> list[Organization]:
        return [_org(r) for r in self.db.query("SELECT * FROM organizations ORDER BY name")]

    def update(self, org_id: str, fields: dict[str, Any]) -> Organization:
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.db.execute(f"UPDATE organizations SET {sets} WHERE id = ?", (*fields.values(), org_id))
        return self.get(org_id)


@dataclass(frozen=True)
class User:
    id: str
    organization_id: str
    username: str
    role: str
    password_hash: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "username": self.username, "role": self.role}


class UserStore:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _user(row) -> User:
        return User(row["id"], row["organization_id"], row["username"], row["role"], row["password_hash"])

    def create(self, org_id: str, username: str, password_hash: str, role: str = "member") -> User:
        uid = new_id("usr")
        self.db.execute("INSERT INTO users (id, organization_id, username, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                        (uid, org_id, username, password_hash, role))
        return self.by_username(username)

    def by_username(self, username: str) -> User | None:
        row = self.db.one("SELECT * FROM users WHERE username = ?", (username,))
        return self._user(row) if row else None

    def list(self, org_id: str) -> list[User]:
        return [self._user(r) for r in self.db.query(
            "SELECT * FROM users WHERE organization_id = ? ORDER BY username COLLATE NOCASE", (org_id,))]

    def set_password(self, user_id: str, password_hash: str) -> None:
        self.db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))

    def delete(self, org_id: str, user_id: str) -> bool:
        return self.db.execute("DELETE FROM users WHERE organization_id = ? AND id = ?", (org_id, user_id)).rowcount == 1

    def count(self) -> int:
        return int(self.db.scalar("SELECT count(*) FROM users"))

    def admins(self, org_id: str) -> int:
        return int(self.db.scalar("SELECT count(*) FROM users WHERE organization_id = ? AND role = 'admin'", (org_id,)))


class TokenStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, org_id: str, name: str, token_hash: str, scope: str = "usage") -> dict[str, Any]:
        tid = new_id("tok")
        self.db.execute("INSERT INTO api_tokens (id, organization_id, name, token_hash, scope) VALUES (?, ?, ?, ?, ?)",
                        (tid, org_id, name, token_hash, scope))
        return {"id": tid, "name": name, "scope": scope}

    def lookup(self, token_hash: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT id, organization_id, scope FROM api_tokens WHERE token_hash = ?", (token_hash,))
        if not row:
            return None
        self.db.execute("UPDATE api_tokens SET last_used_at = datetime('now') WHERE id = ?", (row["id"],))
        return dict(row)

    def list(self, org_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT id, name, scope, created_at, last_used_at FROM api_tokens WHERE organization_id = ? ORDER BY created_at",
            (org_id,))]

    def delete(self, org_id: str, token_id: str) -> bool:
        return self.db.execute("DELETE FROM api_tokens WHERE organization_id = ? AND id = ?",
                               (org_id, token_id)).rowcount == 1


class AuditLog:
    def __init__(self, db: Database):
        self.db = db

    def record(self, org_id: str, actor: str, action: str, entity: str, entity_id: str | None = None,
               detail: dict | None = None) -> None:
        self.db.execute("INSERT INTO audit_log (organization_id, actor, action, entity, entity_id, detail)"
                        " VALUES (?, ?, ?, ?, ?, ?)",
                        (org_id, actor, action, entity, entity_id,
                         json.dumps(detail, ensure_ascii=False, default=str) if detail else None))

    def recent(self, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT actor, action, entity, entity_id, detail, at FROM audit_log WHERE organization_id = ?"
            " ORDER BY id DESC LIMIT ?", (org_id, limit))]

    def purge_older_than(self, days: int) -> int:
        return self.db.execute("DELETE FROM audit_log WHERE at < datetime('now', ?)", (f"-{days} days",)).rowcount


# --- usage & price history ----------------------------------------------------

class UsageStore:
    def __init__(self, db: Database):
        self.db = db

    def add(self, rows: Iterable[tuple[str, str, str, str]]) -> int:
        """rows: (license_id, user_token, occurred_at ISO, source)"""
        rows = list(rows)
        self.db.executemany("INSERT INTO usage_events (license_id, user_token, occurred_at, source) VALUES (?, ?, ?, ?)", rows)
        return len(rows)

    def summary(self, org_id: str, since_iso: str) -> dict[str, dict[str, Any]]:
        """Per license: last use (ever) and distinct users since `since_iso`."""
        rows = self.db.query(
            "SELECT l.id AS license_id, max(u.occurred_at) AS last_used,"
            " count(DISTINCT CASE WHEN u.occurred_at >= ? THEN u.user_token END) AS users"
            " FROM licenses l JOIN usage_events u ON u.license_id = l.id"
            " WHERE l.organization_id = ? GROUP BY l.id", (since_iso, org_id))
        return {r["license_id"]: {"last_used_at": r["last_used"], "active_users": r["users"]} for r in rows}

    def last_used(self, license_id: str) -> str | None:
        return self.db.scalar("SELECT max(occurred_at) FROM usage_events WHERE license_id = ?", (license_id,))

    def purge_older_than(self, days: int) -> int:
        return self.db.execute("DELETE FROM usage_events WHERE occurred_at < datetime('now', ?)",
                               (f"-{days} days",)).rowcount


class PriceHistoryStore:
    def __init__(self, db: Database):
        self.db = db

    def record(self, license_id: str, cost: Decimal, currency: str, cycle: str) -> None:
        self.db.execute("INSERT INTO price_history (license_id, cost, currency, billing_cycle) VALUES (?, ?, ?, ?)",
                        (license_id, str(cost), currency, cycle))

    def changes(self, org_id: str) -> dict[str, list[dict[str, Any]]]:
        rows = self.db.query(
            "SELECT p.license_id, p.cost, p.currency, p.billing_cycle, p.changed_at FROM price_history p"
            " JOIN licenses l ON l.id = p.license_id WHERE l.organization_id = ? ORDER BY p.license_id, p.id",
            (org_id,))
        out: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            out.setdefault(r["license_id"], []).append(dict(r))
        return out


# --- exchange rates -----------------------------------------------------------

class RateStore:
    def __init__(self, db: Database):
        self.db = db

    def all(self) -> dict[str, dict[str, Any]]:
        return {r["currency"]: {"per_eur": Decimal(r["per_eur"]), "rate_date": r["rate_date"],
                                "source": r["source"], "fetched_at": r["fetched_at"]}
                for r in self.db.query("SELECT * FROM exchange_rates")}

    def put(self, currency: str, per_eur: Decimal, rate_date: date | str, source: str) -> None:
        self.db.execute(
            "INSERT INTO exchange_rates (currency, per_eur, rate_date, source, fetched_at)"
            " VALUES (?, ?, ?, ?, datetime('now'))"
            " ON CONFLICT(currency) DO UPDATE SET per_eur=excluded.per_eur, rate_date=excluded.rate_date,"
            " source=excluded.source, fetched_at=excluded.fetched_at"
            # a manual rate is not overwritten by the automatic feed
            " WHERE exchange_rates.source != 'manual' OR excluded.source = 'manual'",
            (currency, str(per_eur), str(rate_date), source))

    def delete(self, currency: str) -> bool:
        return self.db.execute("DELETE FROM exchange_rates WHERE currency = ?", (currency,)).rowcount == 1

    def last_fetch(self) -> str | None:
        return self.db.scalar("SELECT max(fetched_at) FROM exchange_rates WHERE source = 'ecb'")


# --- notifications & webhooks -------------------------------------------------

class NotificationStore:
    def __init__(self, db: Database):
        self.db = db

    def add(self, org_id: str, kind: str, dedupe_key: str, message: str, license_id: str | None = None) -> bool:
        """False when this notification already exists (dedupe)."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO notifications (organization_id, license_id, kind, dedupe_key, message)"
            " VALUES (?, ?, ?, ?, ?)", (org_id, license_id, kind, dedupe_key, message))
        return cur.rowcount == 1

    def list(self, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT id, license_id, kind, message, created_at, read_at FROM notifications"
            " WHERE organization_id = ? ORDER BY id DESC LIMIT ?", (org_id, limit))]

    def unread(self, org_id: str) -> int:
        return int(self.db.scalar("SELECT count(*) FROM notifications WHERE organization_id = ? AND read_at IS NULL",
                                  (org_id,)))

    def mark_read(self, org_id: str, ids: list[int] | None = None) -> int:
        if ids:
            marks = ",".join("?" * len(ids))
            return self.db.execute(f"UPDATE notifications SET read_at = datetime('now') WHERE organization_id = ?"
                                   f" AND read_at IS NULL AND id IN ({marks})", (org_id, *ids)).rowcount
        return self.db.execute("UPDATE notifications SET read_at = datetime('now') WHERE organization_id = ?"
                               " AND read_at IS NULL", (org_id,)).rowcount

    def purge_read_older_than(self, days: int) -> int:
        return self.db.execute("DELETE FROM notifications WHERE read_at IS NOT NULL AND read_at < datetime('now', ?)",
                               (f"-{days} days",)).rowcount


class WebhookStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, org_id: str, url: str, secret: str, events: str) -> dict[str, Any]:
        wid = new_id("whk")
        self.db.execute("INSERT INTO webhooks (id, organization_id, url, secret, events) VALUES (?, ?, ?, ?, ?)",
                        (wid, org_id, url, secret, events))
        return self.get(org_id, wid)

    def get(self, org_id: str, wid: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT id, url, events, active, created_at FROM webhooks WHERE organization_id = ? AND id = ?",
                          (org_id, wid))
        return dict(row) if row else None

    def list(self, org_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT id, url, events, active, created_at FROM webhooks WHERE organization_id = ? ORDER BY created_at",
            (org_id,))]

    def delete(self, org_id: str, wid: str) -> bool:
        return self.db.execute("DELETE FROM webhooks WHERE organization_id = ? AND id = ?", (org_id, wid)).rowcount == 1

    def subscribers(self, org_id: str, event: str) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT id, events FROM webhooks WHERE organization_id = ? AND active = 1", (org_id,))
        return [dict(r) for r in rows if r["events"] == "*" or event in r["events"].split(",")]

    def enqueue(self, webhook_id: str, event: str, payload: dict) -> None:
        self.db.execute("INSERT INTO webhook_deliveries (webhook_id, event, payload) VALUES (?, ?, ?)",
                        (webhook_id, event, json.dumps(payload, ensure_ascii=False, default=str)))

    def due(self, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT d.id, d.event, d.payload, d.attempts, w.url, w.secret, w.id AS webhook_id FROM webhook_deliveries d"
            " JOIN webhooks w ON w.id = d.webhook_id"
            " WHERE d.status = 'pending' AND d.next_attempt_at <= datetime('now') AND w.active = 1"
            " ORDER BY d.next_attempt_at LIMIT ?", (limit,))]

    def mark(self, delivery_id: int, status: str, attempts: int, *, error: str | None = None,
             response_status: int | None = None, retry_in_seconds: int | None = None) -> None:
        self.db.execute(
            "UPDATE webhook_deliveries SET status = ?, attempts = ?, last_error = ?, response_status = ?,"
            " next_attempt_at = datetime('now', ?) WHERE id = ?",
            (status, attempts, error, response_status, f"+{retry_in_seconds or 0} seconds", delivery_id))

    def deliveries(self, org_id: str, wid: str, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT d.id, d.event, d.status, d.attempts, d.last_error, d.response_status, d.created_at"
            " FROM webhook_deliveries d JOIN webhooks w ON w.id = d.webhook_id"
            " WHERE w.organization_id = ? AND w.id = ? ORDER BY d.id DESC LIMIT ?", (org_id, wid, limit))]

    def purge_finished_older_than(self, days: int) -> int:
        return self.db.execute("DELETE FROM webhook_deliveries WHERE status != 'pending' AND created_at < datetime('now', ?)",
                               (f"-{days} days",)).rowcount
