"""Domain model: the License entity, its enums and input validation.

This module has no I/O. Everything else (storage, HTTP, UI) depends on it,
never the other way round.
"""
from __future__ import annotations

import calendar
import re
import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping

MONEY_PLACES = Decimal("0.01")
MAX_COST = Decimal("1000000000")
NAME_MAX = 120
CATEGORY_MAX = 60
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    @property
    def months(self) -> int:
        return _CYCLE_MONTHS[self]


_CYCLE_MONTHS = {
    BillingCycle.MONTHLY: 1,
    BillingCycle.QUARTERLY: 3,
    BillingCycle.YEARLY: 12,
}


class LicenseStatus(str, Enum):
    ACTIVE = "active"        # paid and in use
    INACTIVE = "inactive"    # still paid, but nobody uses it -> savings candidate
    CANCELLED = "cancelled"  # no longer billed

    @property
    def is_billed(self) -> bool:
        return self is not LicenseStatus.CANCELLED


class ValidationError(ValueError):
    """Raised with a field -> message map so callers can show per-field errors."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{k}: {v}" for k, v in self.errors.items()))


@dataclass(frozen=True)
class License:
    id: str
    name: str
    category: str
    cost: Decimal          # amount charged per billing cycle
    currency: str          # ISO 4217 code, e.g. "EUR"
    billing_cycle: BillingCycle
    start_date: date
    status: LicenseStatus
    usage_key: str | None = None   # identifier sent by SSO/login systems; enables usage tracking
    auto_status: bool = True       # usage tracking may switch active <-> inactive automatically

    @property
    def tracked(self) -> bool:
        return self.usage_key is not None

    # --- derived values -------------------------------------------------
    @property
    def monthly_cost(self) -> Decimal:
        """Cost normalised to one month (unrounded; round only for display)."""
        return self.cost / self.billing_cycle.months

    @property
    def yearly_cost(self) -> Decimal:
        return self.cost * (12 // self.billing_cycle.months)

    def is_billed_on(self, day: date) -> bool:
        return self.status.is_billed and self.start_date <= day

    def next_renewal(self, today: date) -> date | None:
        """First charge date on or after `today`; None when cancelled."""
        if not self.status.is_billed:
            return None
        if self.start_date >= today:
            return self.start_date
        step = self.billing_cycle.months
        elapsed = (today.year - self.start_date.year) * 12 + today.month - self.start_date.month
        k = max(elapsed // step, 0)
        candidate = add_months(self.start_date, k * step)
        while candidate < today:
            k += 1
            candidate = add_months(self.start_date, k * step)
        return candidate

    # --- construction / serialisation -----------------------------------
    @classmethod
    def create(cls, data: Mapping[str, Any], *, id: str | None = None) -> "License":
        fields = parse_license_fields(data, partial=False)
        return cls(id=id or new_id(), **fields)

    def updated(self, data: Mapping[str, Any]) -> "License":
        """Return a copy with the given (validated) fields changed."""
        return replace(self, **parse_license_fields(data, partial=True))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "cost": money_str(self.cost),
            "currency": self.currency,
            "billing_cycle": self.billing_cycle.value,
            "start_date": self.start_date.isoformat(),
            "status": self.status.value,
            "usage_key": self.usage_key,
            "auto_status": self.auto_status,
            "monthly_cost": money_str(self.monthly_cost),
        }


# --- helpers -------------------------------------------------------------

def new_id() -> str:
    return uuid.uuid4().hex


def money_str(value: Decimal) -> str:
    return str(value.quantize(MONEY_PLACES))


def add_months(day: date, months: int) -> date:
    """Add months, clamping to the last day (31 Jan + 1 month = 28/29 Feb)."""
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


_REQUIRED = ("name", "category", "cost", "currency", "billing_cycle", "start_date")
_ALLOWED = set(_REQUIRED) | {"status", "usage_key", "auto_status"}
_READ_ONLY = {"id", "monthly_cost", "last_used_at", "active_users_30d"}
_USAGE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def parse_license_fields(data: Mapping[str, Any], *, partial: bool) -> dict[str, Any]:
    """Validate raw input and return typed fields.

    partial=True (PATCH) validates only the keys present; otherwise all
    required keys must be present and `status` defaults to active.
    """
    if not isinstance(data, Mapping):
        raise ValidationError({"_": "Očekuje se JSON objekt."})
    errors: dict[str, str] = {}
    out: dict[str, Any] = {}

    for key in data:
        if key not in _ALLOWED and key not in _READ_ONLY:
            errors[key] = "Nepoznato polje."
    if not partial:
        for key in _REQUIRED:
            if data.get(key) in (None, ""):
                errors[key] = "Obavezno polje."

    def present(key: str) -> bool:
        return key in data and key not in errors

    if present("name"):
        out["name"] = _text(data["name"], NAME_MAX, "name", errors)
    if present("category"):
        out["category"] = _text(data["category"], CATEGORY_MAX, "category", errors)
    if present("cost"):
        out["cost"] = _cost(data["cost"], errors)
    if present("currency"):
        cur = str(data["currency"]).strip().upper()
        if _CURRENCY_RE.match(cur):
            out["currency"] = cur
        else:
            errors["currency"] = "Valuta mora biti troslovni ISO kod (npr. EUR)."
    if present("billing_cycle"):
        out["billing_cycle"] = _enum(BillingCycle, data["billing_cycle"], "billing_cycle", errors)
    if present("start_date"):
        try:
            out["start_date"] = date.fromisoformat(str(data["start_date"]))
        except ValueError:
            errors["start_date"] = "Datum mora biti u obliku GGGG-MM-DD."
    if present("status"):
        out["status"] = _enum(LicenseStatus, data["status"], "status", errors)
    elif not partial:
        out["status"] = LicenseStatus.ACTIVE
    if "usage_key" in data and "usage_key" not in errors:
        raw = data["usage_key"]
        key = None if raw in (None, "") else str(raw).strip().lower()
        if key is not None and not _USAGE_KEY_RE.match(key):
            errors["usage_key"] = "Samo mala slova, brojke, točka, crtica i podvlaka (do 64 znaka)."
        out["usage_key"] = key
    if "auto_status" in data and "auto_status" not in errors:
        if isinstance(data["auto_status"], bool):
            out["auto_status"] = data["auto_status"]
        else:
            errors["auto_status"] = "Očekuje se true ili false."

    if errors:
        raise ValidationError(errors)
    return out


def _text(value: Any, limit: int, key: str, errors: dict[str, str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors[key] = "Obavezno polje."
        return ""
    text = " ".join(value.split())
    if len(text) > limit:
        errors[key] = f"Najviše {limit} znakova."
    return text


def _cost(value: Any, errors: dict[str, str]) -> Decimal:
    if isinstance(value, bool):
        errors["cost"] = "Trošak mora biti broj."
        return Decimal(0)
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        errors["cost"] = "Trošak mora biti broj."
        return Decimal(0)
    if not amount.is_finite() or amount < 0:
        errors["cost"] = "Trošak ne smije biti negativan."
    elif amount >= MAX_COST:
        errors["cost"] = "Trošak je prevelik."
    elif amount.as_tuple().exponent < -2:  # type: ignore[operator]
        errors["cost"] = "Najviše dvije decimale."
    return amount


def _enum(kind: type[Enum], value: Any, key: str, errors: dict[str, str]):
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(m.value for m in kind)  # type: ignore[attr-defined]
        errors[key] = f"Dopuštene vrijednosti: {allowed}."
        return None


# --- Organization (tenant) ----------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    slug: str
    reference_currency: str = "EUR"
    accent: str = "#1238d6"
    inactivity_days: int = 30   # no recorded use for this long -> automatically inactive
    notify_days: int = 14       # notify this many days before a renewal

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "slug": self.slug,
                "reference_currency": self.reference_currency, "accent": self.accent,
                "inactivity_days": self.inactivity_days, "notify_days": self.notify_days}


def parse_org_fields(data: Mapping[str, Any], *, partial: bool) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValidationError({"_": "Očekuje se JSON objekt."})
    allowed = {"name", "slug", "reference_currency", "accent", "inactivity_days", "notify_days"}
    errors: dict[str, str] = {k: "Nepoznato polje." for k in data if k not in allowed | {"id"}}
    out: dict[str, Any] = {}
    if not partial:
        for key in ("name", "slug"):
            if not data.get(key):
                errors[key] = "Obavezno polje."
    if "name" in data and "name" not in errors:
        out["name"] = _text(data["name"], 80, "name", errors)
    if "slug" in data and "slug" not in errors:
        slug = str(data["slug"]).strip().lower()
        if _SLUG_RE.match(slug):
            out["slug"] = slug
        else:
            errors["slug"] = "Mala slova, brojke i crtice (2–40 znakova)."
    if "reference_currency" in data:
        cur = str(data["reference_currency"]).strip().upper()
        if _CURRENCY_RE.match(cur):
            out["reference_currency"] = cur
        else:
            errors["reference_currency"] = "Troslovni ISO kod valute."
    if "accent" in data:
        if isinstance(data["accent"], str) and _COLOR_RE.match(data["accent"]):
            out["accent"] = data["accent"].lower()
        else:
            errors["accent"] = "Boja u obliku #rrggbb."
    for key, lo, hi in (("inactivity_days", 7, 365), ("notify_days", 1, 90)):
        if key in data:
            value = data[key]
            if isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi:
                out[key] = value
            else:
                errors[key] = f"Cijeli broj od {lo} do {hi}."
    if errors:
        raise ValidationError(errors)
    return out
