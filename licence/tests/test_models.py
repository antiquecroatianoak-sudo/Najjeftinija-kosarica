import unittest
from datetime import date
from decimal import Decimal

from licence_app.models import (
    BillingCycle, License, LicenseStatus, ValidationError, add_months,
)

VALID = {
    "name": "Slack Pro", "category": "Komunikacija", "cost": "43.75", "currency": "eur",
    "billing_cycle": "monthly", "start_date": "2025-03-01",
}


class LicenseModelTest(unittest.TestCase):
    def test_create_normalises_and_defaults_status(self):
        lic = License.create({**VALID, "name": "  Slack   Pro "})
        self.assertEqual(lic.name, "Slack Pro")
        self.assertEqual(lic.currency, "EUR")
        self.assertEqual(lic.cost, Decimal("43.75"))
        self.assertIs(lic.status, LicenseStatus.ACTIVE)
        self.assertEqual(len(lic.id), 32)

    def test_monthly_and_yearly_cost_per_cycle(self):
        yearly = License.create({**VALID, "cost": "120", "billing_cycle": "yearly"})
        quarterly = License.create({**VALID, "cost": "30", "billing_cycle": "quarterly"})
        self.assertEqual(yearly.to_dict()["monthly_cost"], "10.00")
        self.assertEqual(quarterly.monthly_cost, Decimal(10))
        self.assertEqual(quarterly.yearly_cost, Decimal(120))

    def test_decimal_comma_and_number_accepted(self):
        self.assertEqual(License.create({**VALID, "cost": "9,99"}).cost, Decimal("9.99"))
        self.assertEqual(License.create({**VALID, "cost": 15}).cost, Decimal(15))

    def test_missing_fields_reported_together(self):
        with self.assertRaises(ValidationError) as ctx:
            License.create({"name": "X"})
        self.assertEqual(set(ctx.exception.errors),
                         {"category", "cost", "currency", "billing_cycle", "start_date"})

    def test_invalid_values(self):
        cases = {
            "cost": ["-1", "abc", "1.999", "NaN", "Infinity", True, "1e12"],
            "currency": ["EU", "euro", "12A"],
            "billing_cycle": ["weekly"],
            "start_date": ["2025-02-30", "1.3.2025"],
            "status": ["paused"],
            "name": ["   ", 5, "x" * 121],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValidationError) as ctx:
                        License.create({**VALID, key: value})
                    self.assertIn(key, ctx.exception.errors)

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            License.create({**VALID, "owner": "ana"})
        self.assertIn("owner", ctx.exception.errors)

    def test_partial_update_keeps_other_fields(self):
        lic = License.create(VALID)
        changed = lic.updated({"status": "inactive"})
        self.assertIs(changed.status, LicenseStatus.INACTIVE)
        self.assertEqual((changed.id, changed.name, changed.cost), (lic.id, lic.name, lic.cost))

    def test_add_months_clamps_to_month_end(self):
        self.assertEqual(add_months(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(add_months(date(2025, 11, 15), 3), date(2026, 2, 15))

    def test_next_renewal(self):
        lic = License.create({**VALID, "start_date": "2025-01-31"})
        self.assertEqual(lic.next_renewal(date(2026, 2, 10)), date(2026, 2, 28))
        self.assertEqual(lic.next_renewal(date(2026, 3, 31)), date(2026, 3, 31))  # no drift after Feb
        yearly = License.create({**VALID, "billing_cycle": "yearly", "start_date": "2024-11-25"})
        self.assertEqual(yearly.next_renewal(date(2026, 11, 12)), date(2026, 11, 25))
        future = License.create({**VALID, "start_date": "2027-01-01"})
        self.assertEqual(future.next_renewal(date(2026, 11, 12)), date(2027, 1, 1))
        cancelled = License.create({**VALID, "status": "cancelled"})
        self.assertIsNone(cancelled.next_renewal(date(2026, 11, 12)))

    def test_cycle_months(self):
        self.assertEqual([c.months for c in BillingCycle], [1, 3, 12])


if __name__ == "__main__":
    unittest.main()
