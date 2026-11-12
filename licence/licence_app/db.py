"""SQLite access and versioned schema migrations.

One connection guarded by a re-entrant lock (WAL keeps reads cheap); every
multi-statement change runs in `transaction()`. Migrations are numbered
functions applied in order inside one transaction each; PRAGMA user_version
records the current version.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

log = logging.getLogger("licence.db")


class Database:
    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._depth = 0
        c = self._conn
        if path != ":memory:":
            c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA temp_store=MEMORY")
        migrate(self)
        c.execute("PRAGMA foreign_keys=ON")

    # --- basic access -----------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, rows)

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        """Atomic block; nested calls join the outer transaction."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self._conn.execute("COMMIT")

    # --- maintenance --------------------------------------------------------
    def optimize(self) -> dict[str, Any]:
        with self._lock:
            self._conn.execute("PRAGMA optimize")
            ok = self._conn.execute("PRAGMA quick_check").fetchone()[0]
            if self.path != ":memory:":
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {"quick_check": ok}

    def backup(self, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(dest))
        try:
            with self._lock:
                self._conn.backup(target)
        finally:
            target.close()
        return dest

    def version(self) -> int:
        return int(self.scalar("PRAGMA user_version"))

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA optimize")
            finally:
                self._conn.close()


# ----------------------------------------------------------------------------
# Migrations
# ----------------------------------------------------------------------------

def _exec_script(conn: sqlite3.Connection, script: str) -> None:
    # Not executescript(): it would COMMIT the surrounding migration transaction.
    # complete_statement() understands comments and string literals containing ';'.
    buffer = ""
    for piece in script.split(";"):
        buffer += piece + ";"
        if sqlite3.complete_statement(buffer):
            if buffer.strip(" \n;"):
                conn.execute(buffer)
            buffer = ""
    if buffer.strip(" \n;"):
        conn.execute(buffer)


def _m1_licenses(conn: sqlite3.Connection) -> None:
    """v1: licenses table (v0.1.0 databases get the *_key columns)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(licenses)")}
    if cols and "name_key" not in cols:
        conn.execute("ALTER TABLE licenses ADD COLUMN name_key TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE licenses ADD COLUMN category_key TEXT NOT NULL DEFAULT ''")
        rows = conn.execute("SELECT id, name, category FROM licenses").fetchall()
        conn.executemany("UPDATE licenses SET name_key = ?, category_key = ? WHERE id = ?",
                         [(n.casefold(), c.casefold(), i) for i, n, c in rows])
        conn.execute("DROP INDEX IF EXISTS licenses_status")
    _exec_script(conn, """
    CREATE TABLE IF NOT EXISTS licenses (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, cost TEXT NOT NULL,
        currency TEXT NOT NULL CHECK (length(currency) = 3),
        billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('monthly','quarterly','yearly')),
        start_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active','inactive','cancelled')),
        name_key TEXT NOT NULL, category_key TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    ) WITHOUT ROWID
    """)


def _m2_multitenant(conn: sqlite3.Connection) -> None:
    """v2: organizations, users, tokens, usage tracking, price history, exchange
    rates, notifications, webhooks, banking, audit log. Licenses move into an
    organization (existing rows go to a default one)."""
    _exec_script(conn, """
    CREATE TABLE organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        reference_currency TEXT NOT NULL DEFAULT 'EUR' CHECK (length(reference_currency) = 3),
        accent TEXT NOT NULL DEFAULT '#1238d6',
        inactivity_days INTEGER NOT NULL DEFAULT 30 CHECK (inactivity_days BETWEEN 7 AND 365),
        notify_days INTEGER NOT NULL DEFAULT 14 CHECK (notify_days BETWEEN 1 AND 90),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin','member')),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX users_org ON users(organization_id);
    CREATE TABLE api_tokens (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        scope TEXT NOT NULL DEFAULT 'usage' CHECK (scope IN ('usage')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_used_at TEXT
    );
    CREATE INDEX api_tokens_org ON api_tokens(organization_id);

    CREATE TABLE licenses_v2 (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        name TEXT NOT NULL, category TEXT NOT NULL, cost TEXT NOT NULL,
        currency TEXT NOT NULL CHECK (length(currency) = 3),
        billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('monthly','quarterly','yearly')),
        start_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active','inactive','cancelled')),
        usage_key TEXT,
        auto_status INTEGER NOT NULL DEFAULT 1 CHECK (auto_status IN (0, 1)),
        tracking_since TEXT,
        name_key TEXT NOT NULL, category_key TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    ) WITHOUT ROWID
    """)
    has_rows = conn.execute("SELECT count(*) FROM licenses").fetchone()[0]
    if has_rows:
        conn.execute("INSERT INTO organizations (id, name, slug) VALUES ('org_default', 'Moja organizacija', 'default')")
    conn.execute("""
        INSERT INTO licenses_v2 (id, organization_id, name, category, cost, currency, billing_cycle,
                                 start_date, status, name_key, category_key, created_at, updated_at)
        SELECT id, 'org_default', name, category, cost, currency, billing_cycle, start_date, status,
               name_key, category_key, created_at, updated_at FROM licenses""")
    _exec_script(conn, """
    DROP TABLE licenses;
    ALTER TABLE licenses_v2 RENAME TO licenses;
    CREATE INDEX licenses_org_status_start ON licenses(organization_id, status, start_date);
    CREATE INDEX licenses_org_category ON licenses(organization_id, category_key);
    CREATE INDEX licenses_org_name ON licenses(organization_id, name_key, id);
    CREATE UNIQUE INDEX licenses_org_usage_key ON licenses(organization_id, usage_key) WHERE usage_key IS NOT NULL;

    CREATE TABLE usage_events (
        id INTEGER PRIMARY KEY,
        license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
        user_token TEXT NOT NULL,      -- HMAC of the user identifier: no e-mails stored
        occurred_at TEXT NOT NULL,     -- UTC 'YYYY-MM-DD HH:MM:SS' (same as SQLite datetime())
        source TEXT NOT NULL DEFAULT 'api'
    );
    CREATE INDEX usage_license_time ON usage_events(license_id, occurred_at);

    CREATE TABLE price_history (
        id INTEGER PRIMARY KEY,
        license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
        cost TEXT NOT NULL, currency TEXT NOT NULL, billing_cycle TEXT NOT NULL,
        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX price_history_license ON price_history(license_id, changed_at);

    CREATE TABLE exchange_rates (
        currency TEXT PRIMARY KEY CHECK (length(currency) = 3),
        per_eur TEXT NOT NULL,         -- units of currency for 1 EUR
        rate_date TEXT NOT NULL,
        source TEXT NOT NULL,          -- 'ecb' | 'manual'
        fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        license_id TEXT REFERENCES licenses(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        dedupe_key TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        read_at TEXT,
        UNIQUE (organization_id, dedupe_key)
    );
    CREATE INDEX notifications_org_unread ON notifications(organization_id, read_at, created_at);

    CREATE TABLE webhooks (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        url TEXT NOT NULL,
        secret TEXT NOT NULL,
        events TEXT NOT NULL,          -- comma separated, '*' = all
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE webhook_deliveries (
        id INTEGER PRIMARY KEY,
        webhook_id TEXT NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
        event TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed')),
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_error TEXT,
        response_status INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX deliveries_due ON webhook_deliveries(status, next_attempt_at);

    CREATE TABLE bank_accounts (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        account_token TEXT NOT NULL,   -- HMAC of the IBAN; the IBAN itself is never stored
        last4 TEXT NOT NULL,
        label TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (organization_id, account_token)
    );
    CREATE TABLE bank_transactions (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        account_id TEXT NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
        fingerprint TEXT NOT NULL,
        booked_on TEXT NOT NULL,
        amount TEXT NOT NULL,          -- negative = money out
        currency TEXT NOT NULL,
        counterparty TEXT NOT NULL,
        description TEXT NOT NULL,     -- card/account numbers masked before storage
        status TEXT NOT NULL DEFAULT 'unmatched' CHECK (status IN ('unmatched','suggested','matched','ignored')),
        license_id TEXT REFERENCES licenses(id) ON DELETE SET NULL,
        match_score REAL,
        match_note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (organization_id, fingerprint)
    );
    CREATE INDEX bank_tx_org_status ON bank_transactions(organization_id, status, booked_on);
    CREATE INDEX bank_tx_license ON bank_transactions(license_id, booked_on);

    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY,
        organization_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX audit_org_at ON audit_log(organization_id, at)
    """)


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_m1_licenses, _m2_multitenant]
SCHEMA_VERSION = len(MIGRATIONS)


def migrate(db: Database) -> int:
    conn = db._conn
    with db._lock:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"Baza ima noviju shemu ({current}) od aplikacije ({SCHEMA_VERSION}).")
        for version in range(current + 1, SCHEMA_VERSION + 1):
            conn.execute("PRAGMA foreign_keys=OFF")  # table rebuilds need it off
            conn.execute("BEGIN IMMEDIATE")
            try:
                MIGRATIONS[version - 1](conn)
                problems = conn.execute("PRAGMA foreign_key_check").fetchall()
                if problems:
                    raise RuntimeError(f"Migracija {version}: neispravne veze {problems[:3]}")
                conn.execute(f"PRAGMA user_version={version}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            log.info("migrated", extra={"fields": {"schema_version": version}})
        return SCHEMA_VERSION
