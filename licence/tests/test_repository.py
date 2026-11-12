import os
import sqlite3
import tempfile
import unittest
from datetime import date

from helpers import make_app, org_with_admin
from licence_app.db import SCHEMA_VERSION, Database
from licence_app.models import License, LicenseStatus
from licence_app.repository import DuplicateUsageKey, LicenseQuery, SQLiteLicenseRepository


def make(**over):
    base = {"name": "App", "category": "Razvoj", "cost": "10", "currency": "EUR",
            "billing_cycle": "monthly", "start_date": "2025-01-01", "status": "active"}
    return License.create({**base, **over})


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.org, _ = org_with_admin(self.app)
        self.other, _ = org_with_admin(self.app, "beta", "bruno")
        self.repo = SQLiteLicenseRepository(self.app.db, self.org.id)
        self.other_repo = SQLiteLicenseRepository(self.app.db, self.other.id)

    def tearDown(self):
        self.app.close()

    def test_crud(self):
        lic = make(name="Figma", cost="12.30", usage_key="figma")
        self.repo.save(lic)
        self.assertEqual(self.repo.get(lic.id), lic)
        self.assertEqual(self.repo.get_by_usage_key("figma"), lic)
        with self.assertRaises(KeyError):
            self.repo.save(lic)
        changed = lic.updated({"status": "inactive", "cost": "0.10", "usage_key": None})
        self.assertTrue(self.repo.update(changed))
        self.assertEqual(self.repo.get(lic.id), changed)
        self.assertTrue(self.repo.delete(lic.id))
        self.assertFalse(self.repo.delete(lic.id))
        self.assertFalse(self.repo.update(changed))

    def test_tenant_isolation(self):
        lic = make(name="Tajno")
        self.repo.save(lic)
        self.assertIsNone(self.other_repo.get(lic.id))
        self.assertEqual(self.other_repo.find(), [])
        self.assertFalse(self.other_repo.update(lic.updated({"name": "Hack"})))
        self.assertFalse(self.other_repo.delete(lic.id))
        self.assertEqual(self.repo.get(lic.id).name, "Tajno")
        # the same usage_key may exist in two organizations, not twice in one
        self.repo.save(make(usage_key="slack"))
        self.other_repo.save(make(usage_key="slack"))
        with self.assertRaises(DuplicateUsageKey):
            self.repo.save(make(usage_key="slack"))

    def test_find_filters_and_order(self):
        for kw in [dict(name="zoom", category="Komunikacija", status="inactive", usage_key="zoom"),
                   dict(name="Šifre", category="Sigurnost"),
                   dict(name="Čuvar", category="sigurnost", status="cancelled"),
                   dict(name="Ana_50%", start_date="2027-01-01"),
                   dict(name="Slack", category="Komunikacija")]:
            self.repo.save(make(**kw))
        names = lambda **q: [l.name for l in self.repo.find(LicenseQuery(**q))]
        self.assertEqual(names(), ["Ana_50%", "Slack", "zoom", "Čuvar", "Šifre"])  # casefold code-point order
        self.assertEqual(names(statuses=(LicenseStatus.INACTIVE,)), ["zoom"])
        self.assertEqual(set(names(category="SIGURNOST")), {"Šifre", "Čuvar"})
        self.assertEqual(names(text="šif"), ["Šifre"])
        self.assertEqual(names(text="_50%"), ["Ana_50%"])
        self.assertNotIn("Ana_50%", names(started_on_or_before=date(2026, 11, 12)))
        self.assertEqual(names(tracked=True), ["zoom"])
        self.assertEqual(self.repo.categories(), ["Komunikacija", "Razvoj", "Sigurnost"])

    def test_tracking_since_set_only_when_tracking_starts(self):
        lic = make(name="X")
        self.repo.save(lic)
        self.assertIsNone(self.repo.tracking_since(lic.id))
        self.repo.update(lic.updated({"usage_key": "x"}))
        first = self.repo.tracking_since(lic.id)
        self.assertIsNotNone(first)
        self.repo.update(self.repo.get(lic.id).updated({"name": "X2"}))
        self.assertEqual(self.repo.tracking_since(lic.id), first)
        self.repo.update(self.repo.get(lic.id).updated({"usage_key": None}))
        self.assertIsNone(self.repo.tracking_since(lic.id))

    def test_queries_use_indexes(self):
        # Every query is an index SEARCH within one organization, never a full-table SCAN
        # across tenants. Which org index the planner picks depends on table statistics.
        queries = [LicenseQuery(statuses=(LicenseStatus.ACTIVE, LicenseStatus.INACTIVE),
                                started_on_or_before=date(2026, 1, 1), ordered=False),
                   LicenseQuery(category="x"), LicenseQuery(text="x"), LicenseQuery(tracked=True), LicenseQuery()]
        for q in queries:
            plan = self.repo.explain(q)
            self.assertRegex(plan, r"SEARCH licenses USING (COVERING )?INDEX licenses_org_\w+ \(organization_id=", q)
            self.assertNotIn("SCAN licenses", plan)
        self.assertNotIn("TEMP B-TREE", self.repo.explain(LicenseQuery()))  # default ORDER BY from the index
        # with statistics on a realistic tenant the status/start index serves the dashboard query
        for i in range(300):
            self.repo.save(make(name=f"L{i}", status="cancelled" if i % 10 else "active"))
        self.app.db.execute("ANALYZE")
        self.assertIn("licenses_org_status_start", self.repo.explain(queries[0]))


class MigrationTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.path)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.path + suffix):
                os.unlink(self.path + suffix)

    def _check(self, db):
        self.assertEqual(db.version(), SCHEMA_VERSION)
        self.assertEqual(db.scalar("PRAGMA foreign_key_check"), None)
        self.assertEqual(db.optimize()["quick_check"], "ok")
        self.assertEqual(db.scalar("PRAGMA journal_mode"), "wal")

    def test_fresh_database(self):
        db = Database(self.path)
        self._check(db)
        db.close()

    def test_from_v0_1_0(self):
        old = sqlite3.connect(self.path)
        old.executescript("""
            CREATE TABLE licenses (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
              cost TEXT NOT NULL, currency TEXT NOT NULL, billing_cycle TEXT NOT NULL,
              start_date TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')));
            CREATE INDEX licenses_status ON licenses(status);
            INSERT INTO licenses (id, name, category, cost, currency, billing_cycle, start_date, status)
            VALUES ('a1', 'Šifre Pro', 'Sigurnost', '9.99', 'EUR', 'monthly', '2025-01-01', 'active');""")
        old.close()
        db = Database(self.path)
        self._check(db)
        repo = SQLiteLicenseRepository(db, "org_default")
        self.assertEqual([l.name for l in repo.find(LicenseQuery(text="ŠIF"))], ["Šifre Pro"])
        self.assertEqual(db.scalar("SELECT slug FROM organizations"), "default")
        db.close()

    def test_from_v1_keeps_rows_and_reopens(self):
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE licenses (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, cost TEXT NOT NULL,
              currency TEXT NOT NULL, billing_cycle TEXT NOT NULL, start_date TEXT NOT NULL, status TEXT NOT NULL,
              name_key TEXT NOT NULL, category_key TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now'))) WITHOUT ROWID;
            INSERT INTO licenses (id, name, category, cost, currency, billing_cycle, start_date, status, name_key, category_key)
            VALUES ('b2', 'Slack', 'Komunikacija', '43.75', 'EUR', 'monthly', '2025-03-01', 'inactive', 'slack', 'komunikacija');
            PRAGMA user_version = 1;""")
        conn.close()
        db = Database(self.path)
        self._check(db)
        lic = SQLiteLicenseRepository(db, "org_default").get("b2")
        self.assertEqual((lic.name, lic.status.value, str(lic.cost)), ("Slack", "inactive", "43.75"))
        db.close()
        db = Database(self.path)   # second open: no migration runs again
        self._check(db)
        db.close()

    def test_newer_schema_is_refused(self):
        conn = sqlite3.connect(self.path)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        conn.close()
        with self.assertRaises(RuntimeError):
            Database(self.path)


if __name__ == "__main__":
    unittest.main()
