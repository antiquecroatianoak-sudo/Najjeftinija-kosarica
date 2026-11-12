import os
import sqlite3
import tempfile
import unittest
from datetime import date

from licence_app.models import License, LicenseStatus
from licence_app.repository import (
    InMemoryLicenseRepository, LicenseQuery, SQLiteLicenseRepository,
)


def make(**over):
    base = {"name": "App", "category": "Razvoj", "cost": "10", "currency": "EUR",
            "billing_cycle": "monthly", "start_date": "2025-01-01", "status": "active"}
    return License.create({**base, **over})


class RepositoryContract:
    """Behaviour every LicenseRepository implementation must have."""

    def make_repo(self):
        raise NotImplementedError

    def setUp(self):
        self.repo = self.make_repo()

    def tearDown(self):
        self.repo.close()

    def test_save_get_update_delete(self):
        lic = make(name="Figma", cost="12.30")
        self.repo.save(lic)
        self.assertEqual(self.repo.get(lic.id), lic)
        with self.assertRaises(KeyError):
            self.repo.save(lic)

        changed = lic.updated({"status": "inactive", "cost": "0.10"})
        self.assertTrue(self.repo.update(changed))
        self.assertEqual(self.repo.get(lic.id), changed)

        self.assertTrue(self.repo.delete(lic.id))
        self.assertIsNone(self.repo.get(lic.id))
        self.assertFalse(self.repo.delete(lic.id))
        self.assertFalse(self.repo.update(changed))

    def test_find_filters_and_order(self):
        for kw in [dict(name="zoom", category="Komunikacija", status="inactive"),
                   dict(name="Šifre", category="Sigurnost"),
                   dict(name="Čuvar", category="sigurnost", status="cancelled"),
                   dict(name="Ana_50%", start_date="2027-01-01"),
                   dict(name="Slack", category="Komunikacija")]:
            self.repo.save(make(**kw))
        names = lambda **q: [l.name for l in self.repo.find(LicenseQuery(**q))]

        # case-insensitive, by code point after casefold (not Croatian alphabetical collation)
        self.assertEqual(names(), ["Ana_50%", "Slack", "zoom", "Čuvar", "Šifre"])
        self.assertEqual(names(statuses=(LicenseStatus.INACTIVE,)), ["zoom"])
        self.assertEqual(set(names(statuses=(LicenseStatus.ACTIVE, LicenseStatus.INACTIVE))),
                         {"Ana_50%", "Šifre", "Slack", "zoom"})
        # Unicode-aware case folding (SQLite NOCASE/lower() would miss Š/Č)
        self.assertEqual(set(names(category="SIGURNOST")), {"Šifre", "Čuvar"})
        self.assertEqual(names(text="šif"), ["Šifre"])
        self.assertEqual(names(text="ČUV"), ["Čuvar"])
        # % and _ are literal, not wildcards
        self.assertEqual(names(text="_50%"), ["Ana_50%"])
        self.assertEqual(names(text="%"), ["Ana_50%"])
        self.assertNotIn("Ana_50%", names(started_on_or_before=date(2026, 11, 12)))
        self.assertEqual(names(text="komunik", statuses=(LicenseStatus.ACTIVE,)), ["Slack"])

    def test_categories_case_insensitive_unique(self):
        for cat in ["sigurnost", "Dizajn", "Sigurnost", "dizajn", "Razvoj"]:
            self.repo.save(make(category=cat))
        self.assertEqual([c.casefold() for c in self.repo.categories()],
                         ["dizajn", "razvoj", "sigurnost"])


class InMemoryRepositoryTest(RepositoryContract, unittest.TestCase):
    def make_repo(self):
        return InMemoryLicenseRepository()


class SQLiteRepositoryTest(RepositoryContract, unittest.TestCase):
    def make_repo(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        return SQLiteLicenseRepository(self.path)

    def tearDown(self):
        super().tearDown()
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.path + suffix):
                os.unlink(self.path + suffix)

    def test_survives_reopen_and_uses_wal(self):
        lic = make(cost="0.10")
        self.repo.save(lic)
        self.repo.close()
        self.repo = SQLiteLicenseRepository(self.path)
        self.assertEqual(self.repo.get(lic.id), lic)
        mode = sqlite3.connect(self.path).execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")

    def test_queries_use_indexes(self):
        plan = self.repo.explain(LicenseQuery(statuses=(LicenseStatus.ACTIVE, LicenseStatus.INACTIVE),
                                              started_on_or_before=date(2026, 1, 1)))
        self.assertIn("licenses_status_start", plan)
        self.assertIn("licenses_category", self.repo.explain(LicenseQuery(category="x")))
        self.assertIn("licenses_name", self.repo.explain(LicenseQuery()))  # ORDER BY without sort step
        self.assertNotIn("TEMP B-TREE", self.repo.explain(LicenseQuery()))

    def test_schema_rejects_bad_rows(self):
        conn = sqlite3.connect(self.path)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO licenses (id, name, category, cost, currency, billing_cycle,"
                         " start_date, status, name_key, category_key)"
                         " VALUES ('x','n','c','1','EUR','weekly','2025-01-01','active','n','c')")
        conn.close()

    def test_migrates_database_from_version_0_1_0(self):
        self.repo.close()
        os.unlink(self.path)
        old = sqlite3.connect(self.path)
        old.executescript("""
            CREATE TABLE licenses (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
              cost TEXT NOT NULL, currency TEXT NOT NULL, billing_cycle TEXT NOT NULL,
              start_date TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')));
            CREATE INDEX licenses_status ON licenses(status);
            INSERT INTO licenses (id, name, category, cost, currency, billing_cycle, start_date, status)
            VALUES ('a1', 'Šifre Pro', 'Sigurnost', '9.99', 'EUR', 'monthly', '2025-01-01', 'active');
        """)
        old.close()
        self.repo = SQLiteLicenseRepository(self.path)
        self.assertEqual([l.name for l in self.repo.find(LicenseQuery(text="ŠIF"))], ["Šifre Pro"])
        version = sqlite3.connect(self.path).execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, 1)


if __name__ == "__main__":
    unittest.main()
