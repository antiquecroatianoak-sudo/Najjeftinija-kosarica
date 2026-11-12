"""License business logic for one organization: CRUD, cost calculations,
detection, ROI and analytics.

Rules
- A license costs money when its status is billed (active or inactive) and it
  has already started. Cancelled licenses never count.
- Per-currency totals are exact. Reference-currency totals use stored exchange
  rates; an amount without a rate is listed as unconverted, never guessed.
- "Expiring": the paid period of a billed license ends (next charge) within N days.
- "Inactive": billed, started, status inactive -> money spent on unused software.
- ROI: "loss" = what inactive licenses cost; "projected saving" = the charges
  they would still incur in the next 12 months (real renewal dates, so a
  yearly plan renewing in 13 months saves nothing this year).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping

from .events import EventBus
from .models import License, LicenseStatus, Organization, ValidationError, add_months, money_str
from .rates import RateService
from .repository import DuplicateUsageKey, LicenseQuery, SQLiteLicenseRepository
from .stores import AuditLog, PriceHistoryStore, UsageStore

DEFAULT_EXPIRY_WINDOW = 30
MAX_EXPIRY_WINDOW = 366
BILLED = (LicenseStatus.ACTIVE, LicenseStatus.INACTIVE)
NEGOTIATION_WINDOW = 90


class NotFound(LookupError):
    pass


# --- pure helpers ---------------------------------------------------------------

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
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    count: dict[str, int] = defaultdict(int)
    for lic in licenses:
        monthly[lic.currency] += lic.monthly_cost
        count[lic.currency] += 1
    return [CurrencyTotal(cur, m, count[cur])
            for cur, m in sorted(monthly.items(), key=lambda kv: (-kv[1], kv[0]))]


def charges_between(lic: License, start: date, end: date) -> list[date]:
    """Charge dates of a billed license in [start, end]."""
    first = lic.next_renewal(start)
    if first is None:
        return []
    out, k = [], 0
    while True:
        # step from the start date (not from the previous charge) to avoid month-end drift
        months_from_start = (first.year - lic.start_date.year) * 12 + first.month - lic.start_date.month
        day = add_months(lic.start_date, months_from_start + k * lic.billing_cycle.months)
        if day > end:
            return out
        if day >= start:
            out.append(day)
        k += 1


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


@dataclass(frozen=True)
class LicenseFilter:
    """Filter from the UI/API: ?status=&category=&q=&expiring=&tracked="""
    status: LicenseStatus | None = None
    category: str | None = None
    query: str | None = None
    expiring_days: int | None = None
    tracked: bool | None = None

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> "LicenseFilter":
        status = params.get("status") or None
        if status is not None:
            try:
                status = LicenseStatus(status)
            except ValueError:
                raise ValidationError({"status": "Nepoznat status."}) from None
        expiring = params.get("expiring")
        tracked = params.get("tracked")
        if tracked not in (None, "", "1", "0"):
            raise ValidationError({"tracked": "Dopušteno 1 ili 0."})
        return cls(status=status,
                   category=(params.get("category") or "").strip() or None,
                   query=(params.get("q") or "").strip() or None,
                   expiring_days=parse_window(expiring) if expiring not in (None, "") else None,
                   tracked=None if tracked in (None, "") else tracked == "1")

    def to_query(self) -> LicenseQuery:
        statuses = (self.status,) if self.status else (BILLED if self.expiring_days is not None else ())
        return LicenseQuery(statuses=statuses, category=self.category, text=self.query, tracked=self.tracked)


# --- service ---------------------------------------------------------------------

class LicenseService:
    def __init__(self, repo: SQLiteLicenseRepository, org: Organization, *, rates: RateService,
                 usage: UsageStore, prices: PriceHistoryStore, audit: AuditLog, events: EventBus,
                 actor: str = "system", today: Callable[[], date] = date.today):
        self.repo, self.org, self.rates = repo, org, rates
        self.usage, self.prices, self.audit, self.events = usage, prices, audit, events
        self.actor = actor
        self._today = today

    def today(self) -> date:
        return self._today()

    # --- reads ------------------------------------------------------------------
    def list(self, flt: LicenseFilter = LicenseFilter()) -> list[License]:
        items = self.repo.find(flt.to_query())
        if flt.expiring_days is not None:
            today = self.today()
            items = [l for l in items
                     if (n := l.next_renewal(today)) is not None and (n - today).days <= flt.expiring_days]
        return items

    def categories(self) -> list[str]:
        return self.repo.categories()

    def get(self, license_id: str) -> License:
        lic = self.repo.get(license_id)
        if lic is None:
            raise NotFound(license_id)
        return lic

    def usage_summary(self) -> dict[str, dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        return self.usage.summary(self.org.id, since)

    def view(self, licenses: list[License]) -> list[dict[str, Any]]:
        """Licenses enriched for display: usage, next renewal, reference-currency cost."""
        usage = self.usage_summary()
        today = self.today()
        out = []
        for lic in licenses:
            d = lic.to_dict()
            u = usage.get(lic.id, {})
            d["last_used_at"] = u.get("last_used_at")
            d["active_users_30d"] = u.get("active_users", 0) if lic.tracked else None
            nxt = lic.next_renewal(today)
            d["next_renewal"] = nxt.isoformat() if nxt else None
            conv = self.rates.convert(lic.monthly_cost, lic.currency, self.org.reference_currency)
            d["monthly_ref"] = money_str(conv.amount) if conv.amount is not None else None
            out.append(d)
        return out

    # --- writes -----------------------------------------------------------------
    def create(self, data: Mapping[str, Any]) -> License:
        lic = License.create(data)
        with self.repo.db.transaction():
            try:
                self.repo.save(lic)
            except DuplicateUsageKey:
                raise ValidationError({"usage_key": "Taj ključ već koristi druga licenca."}) from None
            self.prices.record(lic.id, lic.cost, lic.currency, lic.billing_cycle.value)
            self.audit.record(self.org.id, self.actor, "create", "license", lic.id, {"name": lic.name})
            self.events.publish(self.org.id, "license.created", lic.to_dict())
        return lic

    def replace(self, license_id: str, data: Mapping[str, Any]) -> License:
        old = self.get(license_id)
        return self._update(old, License.create(data, id=license_id))

    def patch(self, license_id: str, data: Mapping[str, Any]) -> License:
        old = self.get(license_id)
        return self._update(old, old.updated(data))

    def set_status(self, lic: License, status: LicenseStatus, *, reason: str) -> License:
        """Status change by the system (usage tracking)."""
        return self._update(lic, lic.updated({"status": status.value}), reason=reason)

    def _update(self, old: License, new: License, reason: str | None = None) -> License:
        with self.repo.db.transaction():
            try:
                if not self.repo.update(new):
                    raise NotFound(new.id)
            except DuplicateUsageKey:
                raise ValidationError({"usage_key": "Taj ključ već koristi druga licenca."}) from None
            if (old.cost, old.currency, old.billing_cycle) != (new.cost, new.currency, new.billing_cycle):
                self.prices.record(new.id, new.cost, new.currency, new.billing_cycle.value)
            changed = {k: [v, new.to_dict()[k]] for k, v in old.to_dict().items() if new.to_dict()[k] != v}
            self.audit.record(self.org.id, self.actor, reason or "update", "license", new.id, changed)
            if reason is None:
                self.events.publish(self.org.id, "license.updated", {**new.to_dict(), "changed": sorted(changed)})
        return new

    def delete(self, license_id: str) -> None:
        lic = self.get(license_id)
        with self.repo.db.transaction():
            if not self.repo.delete(license_id):
                raise NotFound(license_id)
            self.audit.record(self.org.id, self.actor, "delete", "license", license_id, {"name": lic.name})
            self.events.publish(self.org.id, "license.deleted", {"id": license_id, "name": lic.name})

    # --- calculations & detection --------------------------------------------
    def billed_licenses(self) -> list[License]:
        return self.repo.find(LicenseQuery(statuses=BILLED, started_on_or_before=self.today(), ordered=False))

    def monthly_totals(self) -> list[CurrencyTotal]:
        return total_by_currency(self.billed_licenses())

    def detect_inactive(self) -> list[License]:
        items = [l for l in self.billed_licenses() if l.status is LicenseStatus.INACTIVE]
        return sorted(items, key=lambda l: (-l.monthly_cost, l.name.casefold()))

    def detect_expiring(self, days: int = DEFAULT_EXPIRY_WINDOW) -> list[ExpiringLicense]:
        today = self.today()
        out = []
        for lic in self.repo.find(LicenseQuery(statuses=BILLED, ordered=False)):
            renews = lic.next_renewal(today)
            if renews is not None and (renews - today).days <= days:
                out.append(ExpiringLicense(lic, renews, (renews - today).days))
        return sorted(out, key=lambda e: (e.days_left, e.license.name.casefold()))

    def to_reference(self, items: list[tuple[Decimal, str]]) -> dict[str, Any]:
        """Sum (amount, currency) pairs in the reference currency."""
        ref = self.org.reference_currency
        total, missing, dates = Decimal(0), set(), set()
        for amount, cur in items:
            conv = self.rates.convert(amount, cur, ref)
            if conv.amount is None:
                missing.add(cur)
            else:
                total += conv.amount
                if conv.rate_date:
                    dates.add(conv.rate_date)
        return {"currency": ref, "amount": total, "missing_rates": sorted(missing),
                "rate_date": min(dates) if dates else None}

    def roi(self) -> dict[str, Any]:
        today = self.today()
        horizon = today + timedelta(days=365)
        billed = self.billed_licenses()
        inactive = [l for l in billed if l.status is LicenseStatus.INACTIVE]
        spend = self.to_reference([(l.monthly_cost, l.currency) for l in billed])
        loss = self.to_reference([(l.monthly_cost, l.currency) for l in inactive])
        avoidable = self.to_reference([(l.cost * len(charges_between(l, today, horizon)), l.currency)
                                       for l in inactive])
        next_charge = None
        for lic in inactive:
            nxt = lic.next_renewal(today)
            if nxt and (next_charge is None or nxt < next_charge["date"]):
                next_charge = {"date": nxt, "name": lic.name, "cost": money_str(lic.cost), "currency": lic.currency}
        share = (loss["amount"] / spend["amount"] * 100) if spend["amount"] else Decimal(0)
        return {
            "currency": self.org.reference_currency,
            "monthly_spend": money_str(spend["amount"]),
            "monthly_loss": money_str(loss["amount"]),
            "yearly_loss": money_str(loss["amount"] * 12),
            "projected_saving_12m": money_str(avoidable["amount"]),
            "waste_share_pct": str(share.quantize(Decimal("0.1"))),
            "inactive_count": len(inactive),
            "next_avoidable_charge": ({**next_charge, "date": next_charge["date"].isoformat(),
                                       "days": (next_charge["date"] - today).days} if next_charge else None),
            "missing_rates": sorted(set(spend["missing_rates"]) | set(avoidable["missing_rates"])),
            "rate_date": spend["rate_date"],
        }

    def dashboard(self, days: int = DEFAULT_EXPIRY_WINDOW) -> dict[str, Any]:
        today = self.today()
        everything = self.repo.find()
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
        usage = self.usage_summary()
        ref_total = self.to_reference([(l.monthly_cost, l.currency) for l in billed])
        return {
            "as_of": today.isoformat(),
            "window_days": days,
            "organization": self.org.to_dict(),
            "counts": {"total": len(everything), **counts,
                       "tracked": sum(1 for l in everything if l.tracked)},
            "totals": [t.to_dict() for t in total_by_currency(billed)],
            "reference_total": {"currency": ref_total["currency"], "monthly": money_str(ref_total["amount"]),
                                "yearly": money_str(ref_total["amount"] * 12),
                                "missing_rates": ref_total["missing_rates"], "rate_date": ref_total["rate_date"]},
            "roi": self.roi(),
            "inactive": {
                "items": [{"id": l.id, "name": l.name, "category": l.category, "currency": l.currency,
                           "monthly_cost": money_str(l.monthly_cost), "since": l.start_date.isoformat(),
                           "tracked": l.tracked, "last_used_at": usage.get(l.id, {}).get("last_used_at")}
                          for l in inactive],
                "waste": [t.to_dict() for t in total_by_currency(inactive)],
            },
            "by_category": [
                {"category": names[key], "currency": cur, "monthly": money_str(amount)}
                for (key, cur), amount in sorted(by_category.items(), key=lambda kv: (kv[0][1], -kv[1], kv[0][0]))
            ],
            "expiring": [e.to_dict() for e in self.detect_expiring(days)],
        }

    # --- analytics ----------------------------------------------------------------
    def analytics(self) -> dict[str, Any]:
        today = self.today()
        ref = self.org.reference_currency
        horizon_end = add_months(date(today.year, today.month, 1), 12) - timedelta(days=1)
        billed_all = self.repo.find(LicenseQuery(statuses=BILLED, ordered=False))

        months = [add_months(date(today.year, today.month, 1), i) for i in range(12)]
        buckets: dict[str, Decimal] = {m.strftime("%Y-%m"): Decimal(0) for m in months}
        unconverted: set[str] = set()
        for lic in billed_all:
            for day in charges_between(lic, today, horizon_end):
                conv = self.rates.convert(lic.cost, lic.currency, ref)
                if conv.amount is None:
                    unconverted.add(lic.currency)
                else:
                    buckets[day.strftime("%Y-%m")] += conv.amount
        forecast = [{"month": k, "amount": money_str(v)} for k, v in buckets.items()]

        billed = [l for l in billed_all if l.start_date <= today]
        yearly_ref: dict[str, Decimal | None] = {}
        for lic in billed:
            conv = self.rates.convert(lic.yearly_cost, lic.currency, ref)
            yearly_ref[lic.id] = conv.amount
        ranked = sorted((l for l in billed if yearly_ref[l.id] is not None), key=lambda l: -yearly_ref[l.id])
        top = [{"id": l.id, "name": l.name, "category": l.category, "yearly_ref": money_str(yearly_ref[l.id])}
               for l in ranked[:5]]
        top_cut = yearly_ref[ranked[max(len(ranked) // 5 - 1, 0)].id] if len(ranked) >= 3 else None

        price_changes = []
        history = self.prices.changes(self.org.id)
        for lic in billed:
            hist = history.get(lic.id, [])
            if len(hist) < 2:
                continue
            prev, last = hist[-2], hist[-1]
            prev_m = Decimal(prev["cost"]) / _months(prev["billing_cycle"])
            last_m = Decimal(last["cost"]) / _months(last["billing_cycle"])
            if prev["currency"] == last["currency"] and prev_m > 0 and last_m != prev_m:
                pct = (last_m - prev_m) / prev_m * 100
                price_changes.append({"id": lic.id, "name": lic.name, "currency": last["currency"],
                                      "from_monthly": money_str(prev_m), "to_monthly": money_str(last_m),
                                      "change_pct": str(pct.quantize(Decimal("0.1"))), "changed_at": last["changed_at"]})
        increases = {p["id"]: p for p in price_changes if Decimal(p["change_pct"]) > 0}

        usage = self.usage_summary()
        candidates = []
        for lic in billed:
            nxt = lic.next_renewal(today)
            if nxt is None or (nxt - today).days > NEGOTIATION_WINDOW:
                continue
            reasons = []
            if lic.status is LicenseStatus.INACTIVE:
                reasons.append({"code": "inactive", "text": "Plaća se, a ne koristi – otkažite ili smanjite plan."})
            if lic.id in increases:
                reasons.append({"code": "price_increase",
                                "text": f"Cijena porasla {increases[lic.id]['change_pct']} % – tražite staru cijenu."})
            if top_cut is not None and yearly_ref.get(lic.id) is not None and yearly_ref[lic.id] >= top_cut:
                reasons.append({"code": "high_cost", "text": "Među najvećim troškovima – tražite popust za obnovu."})
            if lic.billing_cycle.value == "yearly":
                reasons.append({"code": "annual_renewal", "text": "Godišnja obnova – najbolji trenutak za pregovore."})
            u = usage.get(lic.id)
            if lic.tracked and u is not None:
                reasons.append({"code": "usage", "text": f"{u['active_users']} aktivnih korisnika u 30 dana – uskladite broj mjesta."})
            if reasons:
                candidates.append({"id": lic.id, "name": lic.name, "renews_on": nxt.isoformat(),
                                   "days": (nxt - today).days, "cost": money_str(lic.cost),
                                   "currency": lic.currency, "reasons": reasons,
                                   "yearly_ref": money_str(yearly_ref[lic.id]) if yearly_ref.get(lic.id) is not None else None})
        candidates.sort(key=lambda c: (-len(c["reasons"]), c["days"]))

        return {"currency": ref, "forecast": forecast, "unconverted": sorted(unconverted),
                "top": top, "price_changes": price_changes, "negotiation": candidates}


def _months(cycle: str) -> int:
    return {"monthly": 1, "quarterly": 3, "yearly": 12}[cycle]
