import unittest
from datetime import date

from licence_app.models import ValidationError
from licence_app.repository import InMemoryLicenseRepository
from licence_app.service import LicenseFilter, LicenseService, NotFound, parse_window

TODAY = date(2026, 11, 12)


def lic(**over):
    base = {"name": "App", "category": "Razvoj", "cost": "10", "currency": "EUR",
            "billing_cycle": "monthly", "start_date": "2025-01-01", "status": "active"}
    return {**base, **over}


class CrudTest(unittest.TestCase):
    def setUp(self):
        self.svc = LicenseService(InMemoryLicenseRepository(), today=lambda: TODAY)

    def test_crud_roundtrip(self):
        created = self.svc.create(lic(name="Figma", cost="12.30"))
        self.assertEqual(self.svc.get(created.id), created)
        patched = self.svc.patch(created.id, {"status": "inactive"})
        self.assertEqual((patched.status.value, patched.cost), ("inactive", created.cost))
        replaced = self.svc.replace(created.id, lic(name="Figma Org", cost="45"))
        self.assertEqual((self.svc.get(created.id).name, replaced.status.value), ("Figma Org", "active"))
        self.svc.delete(created.id)
        for call in (lambda: self.svc.get(created.id), lambda: self.svc.delete(created.id),
                     lambda: self.svc.patch(created.id, {"status": "active"}),
                     lambda: self.svc.replace(created.id, lic())):
            with self.assertRaises(NotFound):
                call()

    def test_invalid_patch_does_not_change_record(self):
        created = self.svc.create(lic())
        with self.assertRaises(ValidationError):
            self.svc.patch(created.id, {"cost": "-5"})
        self.assertEqual(self.svc.get(created.id), created)

    def test_filter_params(self):
        self.svc.create(lic(name="Slack", category="Komunikacija"))
        self.svc.create(lic(name="Zoom", category="Komunikacija", status="inactive"))
        self.svc.create(lic(name="GitHub"))
        names = lambda p: [l.name for l in self.svc.list(LicenseFilter.from_params(p))]
        self.assertEqual(names({}), ["GitHub", "Slack", "Zoom"])
        self.assertEqual(names({"status": "inactive"}), ["Zoom"])
        self.assertEqual(names({"category": "komunikacija", "q": "sla"}), ["Slack"])
        with self.assertRaises(ValidationError):
            LicenseFilter.from_params({"status": "x"})


class CalculationTest(unittest.TestCase):
    def setUp(self):
        self.svc = LicenseService(InMemoryLicenseRepository(), today=lambda: TODAY)

    def seed(self):
        self.svc.create(lic(name="Slack", cost="40"))
        self.svc.create(lic(name="Figma", cost="120", billing_cycle="yearly", currency="USD"))
        self.adobe = self.svc.create(lic(name="Adobe", cost="60", status="inactive", category="Dizajn"))
        self.svc.create(lic(name="Zoom", cost="30", billing_cycle="quarterly", status="inactive"))
        self.svc.create(lic(name="Trello", cost="999", status="cancelled"))
        self.svc.create(lic(name="Future", cost="500", start_date="2027-01-01"))

    def test_monthly_totals_per_currency(self):
        self.assertEqual(self.svc.monthly_totals(), [])
        self.seed()
        totals = [t.to_dict() for t in self.svc.monthly_totals()]
        # cancelled and not-yet-started excluded; currencies never mixed
        self.assertEqual(totals, [
            {"currency": "EUR", "monthly": "110.00", "yearly": "1320.00", "count": 3},
            {"currency": "USD", "monthly": "10.00", "yearly": "120.00", "count": 1},
        ])

    def test_yearly_from_monthly_has_no_rounding_drift(self):
        self.svc.create(lic(cost="100", billing_cycle="yearly"))
        self.assertEqual(self.svc.monthly_totals()[0].to_dict()["yearly"], "100.00")

    def test_detect_inactive(self):
        self.seed()
        self.assertEqual([l.name for l in self.svc.detect_inactive()], ["Adobe", "Zoom"])
        self.svc.create(lic(name="Later", status="inactive", start_date="2027-01-01"))
        self.assertNotIn("Later", [l.name for l in self.svc.detect_inactive()])  # not paying yet

    def test_detect_expiring(self):
        self.svc.create(lic(name="Monthly", start_date="2025-01-20"))                # 20.11. -> 8
        self.svc.create(lic(name="Today", start_date="2025-05-12"))                  # 12.11. -> 0
        self.svc.create(lic(name="Idle", start_date="2025-02-01", status="inactive"))  # 1.12. -> 19
        self.svc.create(lic(name="First charge", start_date="2026-11-30"))           # starts -> 18
        self.svc.create(lic(name="Yearly far", billing_cycle="yearly", start_date="2025-06-01"))
        self.svc.create(lic(name="Gone", status="cancelled", start_date="2025-01-20"))
        found = lambda d: [(e.license.name, e.days_left) for e in self.svc.detect_expiring(d)]
        self.assertEqual(found(30), [("Today", 0), ("Monthly", 8), ("First charge", 18), ("Idle", 19)])
        self.assertEqual(found(7), [("Today", 0)])
        self.assertEqual(found(0), [("Today", 0)])
        self.assertIn(("Yearly far", 201), found(366))

    def test_parse_window(self):
        self.assertEqual(parse_window(None), 30)
        self.assertEqual(parse_window("7"), 7)
        for bad in ("-1", "abc", "367", "1.5"):
            with self.assertRaises(ValidationError):
                parse_window(bad)

    def test_dashboard_composes_calculations(self):
        d = self.svc.dashboard()
        self.assertEqual(d["counts"], {"total": 0, "active": 0, "inactive": 0, "cancelled": 0})
        self.assertEqual((d["totals"], d["inactive"]["items"], d["expiring"]), ([], [], []))

        self.seed()
        self.svc.create(lic(name="Mixed case", category="dizajn", cost="5"))
        d = self.svc.dashboard(days=10)
        self.assertEqual(d["window_days"], 10)
        self.assertEqual(d["counts"], {"total": 7, "active": 4, "inactive": 2, "cancelled": 1})
        self.assertEqual(d["totals"], [t.to_dict() for t in self.svc.monthly_totals()])
        self.assertEqual([i["id"] for i in d["inactive"]["items"]][0], self.adobe.id)
        self.assertEqual(d["inactive"]["waste"],
                         [{"currency": "EUR", "monthly": "70.00", "yearly": "840.00", "count": 2}])
        # "Dizajn" and "dizajn" are one category
        self.assertEqual(d["by_category"], [
            {"category": "Dizajn", "currency": "EUR", "monthly": "65.00"},
            {"category": "Razvoj", "currency": "EUR", "monthly": "50.00"},
            {"category": "Razvoj", "currency": "USD", "monthly": "10.00"},
        ])
        self.assertTrue(all(e["days"] <= 10 for e in d["expiring"]))


if __name__ == "__main__":
    unittest.main()
