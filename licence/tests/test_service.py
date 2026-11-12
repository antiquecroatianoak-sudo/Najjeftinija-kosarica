import os
import tempfile
import unittest
from datetime import date

from licence_app.models import ValidationError
from licence_app.repository import InMemoryLicenseRepository, SQLiteLicenseRepository
from licence_app.service import LicenseFilter, LicenseService, NotFound

TODAY = date(2026, 11, 12)


def lic(**over):
    base = {"name": "App", "category": "Razvoj", "cost": "10", "currency": "EUR",
            "billing_cycle": "monthly", "start_date": "2025-01-01", "status": "active"}
    return {**base, **over}


class CrudContract:
    """Same behaviour expected from every repository implementation."""

    def make_repo(self):
        raise NotImplementedError

    def setUp(self):
        self.svc = LicenseService(self.make_repo(), today=lambda: TODAY)

    def test_crud_roundtrip(self):
        created = self.svc.create(lic(name="Figma", cost="12.30"))
        self.assertEqual(self.svc.get(created.id), created)

        patched = self.svc.patch(created.id, {"status": "inactive"})
        self.assertEqual(self.svc.get(created.id).status.value, "inactive")
        self.assertEqual(patched.cost, created.cost)

        replaced = self.svc.replace(created.id, lic(name="Figma Org", cost="45"))
        self.assertEqual(self.svc.get(created.id).name, "Figma Org")
        self.assertEqual(replaced.status.value, "active")

        self.svc.delete(created.id)
        with self.assertRaises(NotFound):
            self.svc.get(created.id)
        with self.assertRaises(NotFound):
            self.svc.delete(created.id)

    def test_missing_ids(self):
        for call in (lambda: self.svc.patch("0" * 32, {"status": "active"}),
                     lambda: self.svc.replace("0" * 32, lic())):
            with self.assertRaises(NotFound):
                call()

    def test_invalid_patch_does_not_change_record(self):
        created = self.svc.create(lic())
        with self.assertRaises(ValidationError):
            self.svc.patch(created.id, {"cost": "-5"})
        self.assertEqual(self.svc.get(created.id), created)

    def test_filtering(self):
        self.svc.create(lic(name="Slack", category="Komunikacija"))
        self.svc.create(lic(name="Zoom", category="Komunikacija", status="inactive"))
        self.svc.create(lic(name="GitHub"))
        names = lambda f: [l.name for l in self.svc.list(LicenseFilter.from_params(f))]
        self.assertEqual(names({}), ["GitHub", "Slack", "Zoom"])
        self.assertEqual(names({"status": "inactive"}), ["Zoom"])
        self.assertEqual(names({"category": "komunikacija"}), ["Slack", "Zoom"])
        self.assertEqual(names({"q": "git"}), ["GitHub"])
        with self.assertRaises(ValidationError):
            LicenseFilter.from_params({"status": "x"})


class InMemoryCrudTest(CrudContract, unittest.TestCase):
    def make_repo(self):
        return InMemoryLicenseRepository()


class SQLiteCrudTest(CrudContract, unittest.TestCase):
    def make_repo(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.repo = SQLiteLicenseRepository(self.path)
        return self.repo

    def tearDown(self):
        self.repo.close()
        os.unlink(self.path)

    def test_persists_across_connections_without_float_drift(self):
        created = self.svc.create(lic(cost="0.10"))
        self.repo.close()
        self.repo = SQLiteLicenseRepository(self.path)
        self.assertEqual(LicenseService(self.repo).get(created.id), created)


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.svc = LicenseService(InMemoryLicenseRepository(), today=lambda: TODAY)

    def test_empty(self):
        d = self.svc.dashboard()
        self.assertEqual(d["counts"], {"total": 0, "active": 0, "inactive": 0, "cancelled": 0})
        self.assertEqual((d["totals"], d["inactive"]["items"], d["renewals"]), ([], [], []))

    def test_totals_per_currency_and_inactive_detection(self):
        self.svc.create(lic(name="Slack", cost="40"))
        self.svc.create(lic(name="Figma", cost="120", billing_cycle="yearly", currency="USD"))
        adobe = self.svc.create(lic(name="Adobe", cost="60", status="inactive", category="Dizajn"))
        self.svc.create(lic(name="Zoom", cost="30", billing_cycle="quarterly", status="inactive"))
        self.svc.create(lic(name="Trello", cost="999", status="cancelled"))
        self.svc.create(lic(name="Future", cost="500", start_date="2027-01-01"))

        d = self.svc.dashboard()
        self.assertEqual(d["counts"], {"total": 6, "active": 3, "inactive": 2, "cancelled": 1})
        # cancelled and not-yet-started are not counted; currencies never mixed
        self.assertEqual(d["totals"], [
            {"currency": "EUR", "monthly": "110.00", "yearly": "1320.00", "count": 3},
            {"currency": "USD", "monthly": "10.00", "yearly": "120.00", "count": 1},
        ])
        self.assertEqual([i["name"] for i in d["inactive"]["items"]], ["Adobe", "Zoom"])
        self.assertEqual(d["inactive"]["items"][0]["id"], adobe.id)
        self.assertEqual(d["inactive"]["waste"],
                         [{"currency": "EUR", "monthly": "70.00", "yearly": "840.00", "count": 2}])
        self.assertEqual(d["by_category"], [
            {"category": "Dizajn", "currency": "EUR", "monthly": "60.00"},
            {"category": "Razvoj", "currency": "EUR", "monthly": "50.00"},
            {"category": "Razvoj", "currency": "USD", "monthly": "10.00"},
        ])

    def test_renewals_within_30_days(self):
        self.svc.create(lic(name="Monthly", start_date="2025-01-20"))                       # 20.11. -> 8 days
        self.svc.create(lic(name="Today", start_date="2025-05-12"))                         # 12.11. -> 0 days
        self.svc.create(lic(name="Yearly far", billing_cycle="yearly", start_date="2025-06-01"))
        self.svc.create(lic(name="Gone", status="cancelled", start_date="2025-01-20"))
        d = self.svc.dashboard()
        self.assertEqual([(r["name"], r["days"]) for r in d["renewals"]], [("Today", 0), ("Monthly", 8)])


if __name__ == "__main__":
    unittest.main()
