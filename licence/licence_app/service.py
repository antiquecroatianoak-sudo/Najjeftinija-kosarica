"""Business logic: CRUD use-cases, cost totals and automatic detection.

Rules
- A license costs money when its status is billed (active or inactive) and it
  has already started. Cancelled licenses never count.
- Amounts are never converted between currencies (no exchange rate is known),
  so every total is per currency.
- "Expiring soon": the currently paid period of a billed license ends (and the
  next charge happens) within `days`. For an inactive license that is the last
  chance to cancel before paying again.
- "Inactive": billed, already started, status inactive -> money spent on a
  license nobody uses.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Mapping

from .models import License, LicenseStatus, ValidationError, money_str
from .repository import LicenseQuery, LicenseRepository

DEFAULT_EXPIRY_WINDOW = 30
MAX_EXPIRY_WINDOW = 366
BILLED = (LicenseStatus.ACTIVE, LicenseStatus.INACTIVE)


class NotFound(LookupError):
    pass


# --- result types ------------------------------------------------------------

@dataclass(frozen=True)
class CurrencyTotal:
    currency: str
    monthly: Decimal
    count: int

    @property
    def yearly(self) -> Decimal:
        return self.monthly * 12

    def to_dict(self) -> dict[str, Any]:
        return {"currency": self.currency, "monthly": money_str(self.monthly),
                "yearly": money_str(self.yearly), "count": self.count}


@dataclass(frozen=True)
class ExpiringLicense:
    license: License
    renews_on: date
    days_left: int

    def to_dict(self) -> dict[str, Any]:
        lic = self.license
        return {"id": lic.id, "name": lic.name, "date": self.renews_on.isoformat(),
                "days": self.days_left, "cost": money_str(lic.cost), "currency": lic.currency,
                "status": lic.status.value}


def total_by_currency(licenses: list[License]) -> list[CurrencyTotal]:
    """Monthly sums per currency, largest first (pure function)."""
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    count: dict[str, int] = defaultdict(int)
    for lic in licenses:
        monthly[lic.currency] += lic.monthly_cost
        count[lic.currency] += 1
    return [CurrencyTotal(cur, m, count[cur])
            for cur, m in sorted(monthly.items(), key=lambda kv: (-kv[1], kv[0]))]


def parse_window(value: str | int | None) -> int:
    if value in (None, ""):
        return DEFAULT_EXPIRY_WINDOW
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = -1
    if not 0 <= days <= MAX_EXPIRY_WINDOW:
        raise ValidationError({"days": f"Broj dana mora biti od 0 do {MAX_EXPIRY_WINDOW}."})
    return days


# --- service -----------------------------------------------------------------

@dataclass(frozen=True)
class LicenseFilter:
    """Filter as received from the UI/API (?status=&category=&q=)."""
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
        return cls(status=status,
                   category=(params.get("category") or "").strip() or None,
                   query=(params.get("q") or "").strip() or None)

    def to_query(self) -> LicenseQuery:
        return LicenseQuery(statuses=(self.status,) if self.status else (),
                            category=self.category, text=self.query)


class LicenseService:
    def __init__(self, repo: LicenseRepository, today: Callable[[], date] = date.today):
        self._repo = repo
        self._today = today

    # --- CRUD -------------------------------------------------------------
    def list(self, flt: LicenseFilter = LicenseFilter()) -> list[License]:
        return self._repo.find(flt.to_query())

    def categories(self) -> list[str]:
        return self._repo.categories()

    def get(self, license_id: str) -> License:
        lic = self._repo.get(license_id)
        if lic is None:
            raise NotFound(license_id)
        return lic

    def create(self, data: Mapping[str, Any]) -> License:
        lic = License.create(data)
        self._repo.save(lic)
        return lic

    def replace(self, license_id: str, data: Mapping[str, Any]) -> License:
        """Full update (PUT): all required fields must be supplied."""
        self.get(license_id)
        return self._update(License.create(data, id=license_id))

    def patch(self, license_id: str, data: Mapping[str, Any]) -> License:
        return self._update(self.get(license_id).updated(data))

    def delete(self, license_id: str) -> None:
        if not self._repo.delete(license_id):
            raise NotFound(license_id)

    def _update(self, lic: License) -> License:
        if not self._repo.update(lic):
            raise NotFound(lic.id)
        return lic

    # --- calculations and detection --------------------------------------
    def billed_licenses(self) -> list[License]:
        return self._repo.find(LicenseQuery(statuses=BILLED, started_on_or_before=self._today()))

    def monthly_totals(self) -> list[CurrencyTotal]:
        """Total monthly cost of everything currently billed, per currency."""
        return total_by_currency(self.billed_licenses())

    def detect_inactive(self) -> list[License]:
        """Billed but unused licenses, most expensive (per month) first."""
        items = [l for l in self.billed_licenses() if l.status is LicenseStatus.INACTIVE]
        return sorted(items, key=lambda l: (-l.monthly_cost, l.name.casefold()))

    def detect_expiring(self, days: int = DEFAULT_EXPIRY_WINDOW) -> list[ExpiringLicense]:
        """Billed licenses whose paid period ends within `days` (soonest first).
        Includes not-yet-started ones whose first charge falls in the window."""
        today = self._today()
        out = []
        for lic in self._repo.find(LicenseQuery(statuses=BILLED)):
            renews = lic.next_renewal(today)
            if renews is not None and (renews - today).days <= days:
                out.append(ExpiringLicense(lic, renews, (renews - today).days))
        return sorted(out, key=lambda e: (e.days_left, e.license.name.casefold()))

    # --- dashboard --------------------------------------------------------
    def dashboard(self, days: int = DEFAULT_EXPIRY_WINDOW) -> dict[str, Any]:
        today = self._today()
        everything = self._repo.find()
        billed = [l for l in everything if l.status in BILLED and l.start_date <= today]
        inactive = sorted((l for l in billed if l.status is LicenseStatus.INACTIVE),
                          key=lambda l: (-l.monthly_cost, l.name.casefold()))

        counts = {s.value: 0 for s in LicenseStatus}
        for lic in everything:
            counts[lic.status.value] += 1

        by_category: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        names: dict[str, str] = {}
        for lic in billed:
            key = lic.category.casefold()
            names.setdefault(key, lic.category)
            by_category[(key, lic.currency)] += lic.monthly_cost

        return {
            "as_of": today.isoformat(),
            "window_days": days,
            "counts": {"total": len(everything), **counts},
            "totals": [t.to_dict() for t in total_by_currency(billed)],
            "inactive": {
                "items": [{"id": l.id, "name": l.name, "category": l.category,
                           "currency": l.currency, "monthly_cost": money_str(l.monthly_cost),
                           "since": l.start_date.isoformat()} for l in inactive],
                "waste": [t.to_dict() for t in total_by_currency(inactive)],
            },
            "by_category": [
                {"category": names[key], "currency": cur, "monthly": money_str(amount)}
                for (key, cur), amount in sorted(by_category.items(),
                                                 key=lambda kv: (kv[0][1], -kv[1], kv[0][0]))
            ],
            "expiring": [e.to_dict() for e in self.detect_expiring(days)],
        }
