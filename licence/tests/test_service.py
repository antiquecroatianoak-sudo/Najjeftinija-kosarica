import unittest
from datetime import date

from helpers import TODAY, license_data as lic, make_app, org_with_admin
from licence_app.models import ValidationError
from licence_app.service import LicenseFilter, NotFound, charges_between, parse_window
from licence_app.models import License


class ServiceBase(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.org, self.user = org_with_admin(self.app)
        self.ws = self.app.workspace(self.org, "ana")
        self.svc = self.ws.licenses

    def tearDown(self):
        self.app.close()

    def seed(self):
        self.svc.create(lic(name="Slack", cost="40"))
        self.svc.create(lic(name="Figma", cost="120", billing_cycle="yearly", currency="USD"))
        self.adobe = self.svc.create(lic(name="Adobe", cost="60", status="inactive", category="Dizajn"))
        self.svc.create(lic(name="Zoom", cost="30", billing_cycle="quarterly", status="inactive"))
        self.svc.create(lic(name="Trello", cost="999", status="cancelled"))
        self.svc.create(lic(name="Future", cost="500", start_date="2027-01-01"))


class CrudTest(ServiceBase):
    def test_crud_with_audit_price_history_and_events(self):
        created = self.svc.create(lic(name="Figma", cost="12.30"))
        self.assertEqual(self.svc.get(created.id), created)
        self.svc.patch(created.id, {"status": "inactive"})
        self.svc.patch(created.id, {"cost": "15"})
        replaced = self.svc.replace(created.id, lic(name="Figma Org", cost="45"))
        self.assertEqual(replaced.status.value, "active")
        history = self.app.prices.changes(self.org.id)[created.id]
        self.assertEqual([h["cost"] for h in history], ["12.30", "15", "45"])  # status change is not a price change
        actions = [a["action"] for a in self.app.audit.recent(self.org.id)]
        self.assertEqual(actions[:4], ["update", "update", "update", "create"])
        self.svc.delete(created.id)
        for call in (lambda: self.svc.get(created.id), lambda: self.svc.delete(created.id),
                     lambda: self.svc.patch(created.id, {"status": "active"})):
            with self.assertRaises(NotFound):
                call()

    def test_duplicate_usage_key_is_a_field_error(self):
        self.svc.create(lic(name="A", usage_key="slack"))
        with self.assertRaises(ValidationError) as ctx:
            self.svc.create(lic(name="B", usage_key="slack"))
        self.assertIn("usage_key", ctx.exception.errors)

    def test_invalid_patch_does_not_change_record(self):
        created = self.svc.create(lic())
        with self.assertRaises(ValidationError):
            self.svc.patch(created.id, {"cost": "-5"})
        self.assertEqual(self.svc.get(created.id), created)

    def test_filters_including_quick_filters(self):
        self.svc.create(lic(name="Slack", category="Komunikacija", start_date="2025-01-20", usage_key="slack"))
        self.svc.create(lic(name="Zoom", category="Komunikacija", status="inactive", start_date="2025-03-05"))
        self.svc.create(lic(name="GitHub", start_date="2025-06-01", billing_cycle="yearly"))
        names = lambda p: [l.name for l in self.svc.list(LicenseFilter.from_params(p))]
        self.assertEqual(names({}), ["GitHub", "Slack", "Zoom"])
        self.assertEqual(names({"status": "inactive"}), ["Zoom"])
        self.assertEqual(names({"category": "komunikacija", "q": "sla"}), ["Slack"])
        self.assertEqual(names({"expiring": "30"}), ["Slack", "Zoom"])   # 20.11. and 5.12.
        self.assertEqual(names({"expiring": "10"}), ["Slack"])
        self.assertEqual(names({"tracked": "1"}), ["Slack"])
        for bad in ({"status": "x"}, {"expiring": "999"}, {"tracked": "yes"}):
            with self.assertRaises(ValidationError):
                LicenseFilter.from_params(bad)


class CalculationTest(ServiceBase):
    def test_totals_per_currency_and_reference(self):
        self.assertEqual(self.svc.monthly_totals(), [])
        self.seed()
        self.assertEqual([t.to_dict() for t in self.svc.monthly_totals()], [
            {"currency": "EUR", "monthly": "110.00", "yearly": "1320.00", "count": 3},
            {"currency": "USD", "monthly": "10.00", "yearly": "120.00", "count": 1},
        ])
        d = self.svc.dashboard()
        self.assertEqual(d["reference_total"]["missing_rates"], ["USD"])   # no rates yet: not guessed
        self.assertEqual(d["reference_total"]["monthly"], "110.00")
        self.app.rates.refresh()                                           # fixture: 1 EUR = 1.08 USD
        d = self.svc.dashboard()
        self.assertEqual(d["reference_total"], {"currency": "EUR", "monthly": "119.26", "yearly": "1431.11",
                                                "missing_rates": [], "rate_date": "2026-11-11"})

    def test_detect_inactive_and_expiring(self):
        self.seed()
        self.assertEqual([l.name for l in self.svc.detect_inactive()], ["Adobe", "Zoom"])
        found = [(e.license.name, e.days_left) for e in self.svc.detect_expiring(30)]
        self.assertEqual(found, [("Adobe", 19), ("Slack", 19)])   # Zoom (quarterly) next charges 1.1.2027
        self.assertEqual(self.svc.detect_expiring(7), [])

    def test_roi(self):
        self.seed()
        roi = self.svc.roi()
        self.assertEqual(roi["monthly_loss"], "70.00")            # Adobe 60 + Zoom 30/3
        self.assertEqual(roi["yearly_loss"], "840.00")
        # next 12 months: Adobe 12 x 60, Zoom quarterly 4 x 30 -> 840
        self.assertEqual(roi["projected_saving_12m"], "840.00")
        self.assertEqual(roi["next_avoidable_charge"]["days"], 19)
        self.assertEqual(roi["inactive_count"], 2)

    def test_roi_counts_real_charges_for_yearly_plans(self):
        self.svc.create(lic(name="Late", cost="1200", billing_cycle="yearly", status="inactive",
                            start_date="2025-12-20"))   # next charge 20.12.2026, then 20.12.2027
        self.assertEqual(self.svc.roi()["projected_saving_12m"], "1200.00")
        self.assertEqual(self.svc.roi()["monthly_loss"], "100.00")

    def test_charges_between_month_end(self):
        l = License.create(lic(start_date="2025-01-31"))
        days = charges_between(l, date(2026, 1, 1), date(2026, 4, 30))
        self.assertEqual(days, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)])

    def test_analytics(self):
        self.seed()
        self.app.rates.refresh()
        self.svc.patch(self.adobe.id, {"cost": "66"})
        a = self.svc.analytics()
        self.assertEqual(len(a["forecast"]), 12)
        self.assertEqual(a["forecast"][0]["month"], "2026-11")
        self.assertEqual(a["top"][0]["name"], "Adobe")
        change = next(p for p in a["price_changes"] if p["name"] == "Adobe")
        self.assertEqual(change["change_pct"], "10.0")
        adobe = next(c for c in a["negotiation"] if c["name"] == "Adobe")
        self.assertEqual({r["code"] for r in adobe["reasons"]}, {"inactive", "price_increase", "high_cost"})
        self.assertEqual(a["negotiation"][0]["name"], "Adobe")   # most reasons first

    def test_parse_window(self):
        self.assertEqual(parse_window(None), 30)
        for bad in ("-1", "abc", "367"):
            with self.assertRaises(ValidationError):
                parse_window(bad)


if __name__ == "__main__":
    unittest.main()
