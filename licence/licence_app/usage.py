"""Usage tracking: replaces manual status updates.

Login/SSO systems (or any script) POST usage events for a license, identified
by its `usage_key` (e.g. "slack") or id. User identifiers are tokenised
(HMAC) before storage.

Automatic status (only for licenses with a usage_key and auto_status=true):
- active   -> inactive when nobody used it for `inactivity_days`
              (counted from tracking start if it was never used);
- inactive -> active as soon as a usage event arrives.
Cancelled licenses are never touched.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .models import License, LicenseStatus, ValidationError
from .repository import LicenseQuery
from .security import Tokenizer
from .service import LicenseService
from .stores import UsageStore

MAX_EVENTS = 1000
MAX_AGE_DAYS = 400


def _parse_time(value: Any, now: datetime) -> datetime:
    if value in (None, ""):
        return now
    try:
        text = str(value).replace("Z", "+00:00")
        when = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("Vrijeme mora biti ISO 8601 (npr. 2026-11-12T08:30:00Z).") from None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    if when > now + timedelta(minutes=5):
        raise ValueError("Vrijeme je u budućnosti.")
    if when < now - timedelta(days=MAX_AGE_DAYS):
        raise ValueError("Događaj je stariji od 400 dana.")
    return when


class UsageService:
    def __init__(self, licenses: LicenseService, store: UsageStore, tokenizer: Tokenizer,
                 now=lambda: datetime.now(timezone.utc)):
        self.licenses, self.store, self.tokenizer, self.now = licenses, store, tokenizer, now

    def ingest(self, payload: Any, source: str = "api") -> dict[str, Any]:
        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list) or not events:
            raise ValidationError({"events": "Očekuje se neprazan popis events."})
        if len(events) > MAX_EVENTS:
            raise ValidationError({"events": f"Najviše {MAX_EVENTS} događaja po zahtjevu."})
        now = self.now()
        repo = self.licenses.repo
        rows, unknown, errors, touched = [], set(), [], {}
        for i, ev in enumerate(events):
            if not isinstance(ev, dict):
                errors.append({"index": i, "error": "Događaj mora biti objekt."})
                continue
            ref = str(ev.get("license") or "").strip()
            user = str(ev.get("user") or "").strip()
            if not ref or not user or len(user) > 200:
                errors.append({"index": i, "error": "Obavezno: license (usage_key ili id) i user (do 200 znakova)."})
                continue
            try:
                when = _parse_time(ev.get("at"), now)
            except ValueError as e:
                errors.append({"index": i, "error": str(e)})
                continue
            lic = touched.get(ref) or repo.get_by_usage_key(ref.lower()) or repo.get(ref)
            if lic is None:
                unknown.add(ref)
                continue
            touched[ref] = lic
            rows.append((lic.id, self.tokenizer.user(user), when.strftime("%Y-%m-%d %H:%M:%S"),
                         str(ev.get("source") or source)[:40]))

        reactivated = []
        with repo.db.transaction():
            accepted = self.store.add(rows)
            for lic in {l.id: l for l in touched.values()}.values():
                if lic.status is LicenseStatus.INACTIVE and lic.auto_status and lic.tracked:
                    self.licenses.set_status(lic, LicenseStatus.ACTIVE, reason="auto_reactivate")
                    self.licenses.events.publish(
                        self.licenses.org.id, "license.reactivated", {"id": lic.id, "name": lic.name},
                        notify=f"„{lic.name}” se ponovno koristi – status je automatski vraćen na aktivno.",
                        dedupe_key=f"reactivated:{lic.id}:{now:%Y-%m-%dT%H:%M}", license_id=lic.id)
                    reactivated.append(lic.id)
        return {"accepted": accepted, "unknown": sorted(unknown), "errors": errors, "reactivated": reactivated}

    def auto_inactivate(self) -> list[str]:
        """Mark tracked, auto-managed active licenses without recent use as inactive."""
        org = self.licenses.org
        limit = self.now() - timedelta(days=org.inactivity_days)
        changed = []
        for lic in self.licenses.repo.find(LicenseQuery(statuses=(LicenseStatus.ACTIVE,), tracked=True)):
            if not lic.auto_status:
                continue
            last = self.store.last_used(lic.id) or self.licenses.repo.tracking_since(lic.id)
            if last is None:
                continue
            last_dt = datetime.fromisoformat(last.replace(" ", "T")).replace(tzinfo=timezone.utc)
            if last_dt >= limit:
                continue
            self.licenses.set_status(lic, LicenseStatus.INACTIVE, reason="auto_inactivate")
            days = (self.now() - last_dt).days
            self.licenses.events.publish(
                org.id, "license.auto_inactive",
                {"id": lic.id, "name": lic.name, "unused_days": days, "monthly_cost": str(lic.monthly_cost),
                 "currency": lic.currency},
                notify=f"„{lic.name}” se ne koristi {days} dana – automatski označena kao neaktivna.",
                dedupe_key=f"auto_inactive:{lic.id}:{last}", license_id=lic.id)
            changed.append(lic.id)
        return changed


def notify_expiring(licenses: LicenseService) -> int:
    """Smart renewal notices: one per license and renewal date, within notify_days."""
    org = licenses.org
    sent = 0
    for e in licenses.detect_expiring(org.notify_days):
        lic: License = e.license
        when = "danas" if e.days_left == 0 else f"za {e.days_left} d. ({e.renews_on:%d.%m.%Y.})"
        if lic.status is LicenseStatus.INACTIVE:
            text = f"„{lic.name}” se naplaćuje {when}, a ne koristi se – otkažite prije naplate ({lic.cost} {lic.currency})."
        else:
            text = f"„{lic.name}” se obnavlja {when}: {lic.cost} {lic.currency}."
        if licenses.events.publish(org.id, "license.expiring", {**e.to_dict(), "inactive": lic.status is LicenseStatus.INACTIVE},
                                   notify=text, dedupe_key=f"expiring:{lic.id}:{e.renews_on}", license_id=lic.id):
            sent += 1
    return sent
