"""Business logic: CRUD use-cases and the dashboard summary.

Costs are never converted between currencies (no exchange rate is known),
so every total is reported per currency.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Mapping

from .models import License, LicenseStatus, ValidationError, money_str
from .repository import LicenseRepository

RENEWAL_WINDOW_DAYS = 30


class NotFound(LookupError):
    pass


@dataclass(frozen=True)
class LicenseFilter:
    status: LicenseStatus | None = None
    category: str | None = None
    query: str | None = None

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> "LicenseFilter":
        status = params.get("status") or None
        if status is not None:
            try:
                status = LicenseStatus(status)
            except ValueError:
                raise ValidationError({"status": "Nepoznat status."}) from None
        return cls(
            status=status,
            category=(params.get("category") or "").strip() or None,
            query=(params.get("q") or "").strip().lower() or None,
        )

    def matches(self, lic: License) -> bool:
        if self.status and lic.status is not self.status:
            return False
        if self.category and lic.category.lower() != self.category.lower():
            return False
        if self.query and self.query not in f"{lic.name} {lic.category}".lower():
            return False
        return True


class LicenseService:
    def __init__(self, repo: LicenseRepository, today: Callable[[], date] = date.today):
        self._repo = repo
        self._today = today

    # --- CRUD -------------------------------------------------------------
    def list(self, flt: LicenseFilter = LicenseFilter()) -> list[License]:
        items = [lic for lic in self._repo.list() if flt.matches(lic)]
        return sorted(items, key=lambda l: (l.name.lower(), l.id))

    def get(self, license_id: str) -> License:
        lic = self._repo.get(license_id)
        if lic is None:
            raise NotFound(license_id)
        return lic

    def create(self, data: Mapping[str, Any]) -> License:
        lic = License.create(data)
        self._repo.add(lic)
        return lic

    def replace(self, license_id: str, data: Mapping[str, Any]) -> License:
        """Full update (PUT): all required fields must be supplied."""
        self.get(license_id)
        lic = License.create(data, id=license_id)
        self._save(lic)
        return lic

    def patch(self, license_id: str, data: Mapping[str, Any]) -> License:
        lic = self.get(license_id).updated(data)
        self._save(lic)
        return lic

    def delete(self, license_id: str) -> None:
        if not self._repo.delete(license_id):
            raise NotFound(license_id)

    def _save(self, lic: License) -> None:
        if not self._repo.update(lic):
            raise NotFound(lic.id)

    # --- dashboard --------------------------------------------------------
    def dashboard(self) -> dict[str, Any]:
        today = self._today()
        items = self._repo.list()
        billed = [l for l in items if l.is_billed_on(today)]
        inactive = sorted(
            (l for l in billed if l.status is LicenseStatus.INACTIVE),
            key=lambda l: l.monthly_cost, reverse=True,
        )

        counts = {s.value: 0 for s in LicenseStatus}
        for lic in items:
            counts[lic.status.value] += 1

        by_category: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for lic in billed:
            by_category[(lic.category, lic.currency)] += lic.monthly_cost

        renewals = []
        for lic in items:
            nxt = lic.next_renewal(today)
            if nxt is not None and (nxt - today).days <= RENEWAL_WINDOW_DAYS:
                renewals.append({
                    "id": lic.id, "name": lic.name, "date": nxt.isoformat(),
                    "days": (nxt - today).days, "cost": money_str(lic.cost),
                    "currency": lic.currency, "status": lic.status.value,
                })
        renewals.sort(key=lambda r: (r["days"], r["name"].lower()))

        return {
            "as_of": today.isoformat(),
            "counts": {"total": len(items), **counts},
            "totals": _totals(billed),
            "inactive": {
                "items": [
                    {
                        "id": l.id, "name": l.name, "category": l.category,
                        "currency": l.currency, "monthly_cost": money_str(l.monthly_cost),
                        "since": l.start_date.isoformat(),
                    }
                    for l in inactive
                ],
                "waste": _totals(inactive),
            },
            "by_category": [
                {"category": cat, "currency": cur, "monthly": money_str(amount)}
                for (cat, cur), amount in sorted(by_category.items(), key=lambda kv: (kv[0][1], -kv[1], kv[0][0].lower()))
            ],
            "renewals": renewals,
        }


def _totals(items: list[License]) -> list[dict[str, Any]]:
    """Monthly / yearly sums per currency, largest first."""
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    count: dict[str, int] = defaultdict(int)
    for lic in items:
        monthly[lic.currency] += lic.monthly_cost
        count[lic.currency] += 1
    return [
        {"currency": cur, "monthly": money_str(m), "yearly": money_str(m * 12), "count": count[cur]}
        for cur, m in sorted(monthly.items(), key=lambda kv: -kv[1])
    ]
