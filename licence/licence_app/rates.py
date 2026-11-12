"""Exchange rates and conversion to an organization's reference currency.

Source: the ECB euro foreign exchange reference rates (free, published on
working days around 16:00 CET). Rates are stored as "units per 1 EUR"; any
pair converts through EUR. Manual rates (for currencies the ECB does not
publish) take precedence and are never overwritten by the feed.

A missing rate is never guessed: the amount is reported as unconverted.
"""
from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable

from .models import ValidationError
from .stores import RateStore
from .xmlsafe import fromstring, local

log = logging.getLogger("licence.rates")
Fetcher = Callable[[str], bytes]
MAX_FEED_BYTES = 512 * 1024


def http_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LicensePulse/1.0 (exchange-rates)"})
    with urllib.request.urlopen(req, timeout=15) as res:  # noqa: S310 (URL is operator configuration)
        return res.read(MAX_FEED_BYTES + 1)[:MAX_FEED_BYTES]


def parse_ecb(xml_bytes: bytes) -> tuple[date, dict[str, Decimal]]:
    """Parse eurofxref-daily.xml (namespaces ignored)."""
    root = fromstring(xml_bytes, MAX_FEED_BYTES)
    day, rates = None, {}
    for el in root.iter():
        if local(el.tag) != "Cube":
            continue
        if "time" in el.attrib:
            day = date.fromisoformat(el.attrib["time"])
        if "currency" in el.attrib and "rate" in el.attrib:
            try:
                value = Decimal(el.attrib["rate"])
            except InvalidOperation:
                continue
            if value > 0 and len(el.attrib["currency"]) == 3:
                rates[el.attrib["currency"].upper()] = value
    if day is None or not rates:
        raise ValueError("ECB feed: no rates found")
    return day, rates


@dataclass
class Converted:
    amount: Decimal | None   # None = no rate available
    rate_date: str | None


class RateService:
    def __init__(self, store: RateStore, url: str, fetch: Fetcher = http_fetch):
        self.store, self.url, self.fetch = store, url, fetch
        self._cache: dict | None = None

    def table(self) -> dict[str, dict]:
        if self._cache is None:
            table = self.store.all()
            table.setdefault("EUR", {"per_eur": Decimal(1), "rate_date": None, "source": "base", "fetched_at": None})
            self._cache = table
        return self._cache

    def _invalidate(self) -> None:
        self._cache = None

    def refresh(self) -> dict:
        """Download and store the ECB rates. Raises on network/format errors."""
        day, rates = parse_ecb(self.fetch(self.url))
        for cur, value in rates.items():
            self.store.put(cur, value, day, "ecb")
        self._invalidate()
        log.info("rates_refreshed", extra={"fields": {"date": str(day), "currencies": len(rates)}})
        return {"date": str(day), "currencies": len(rates)}

    def set_manual(self, currency: str, per_eur) -> None:
        cur = str(currency).upper()
        try:
            value = Decimal(str(per_eur).replace(",", "."))
        except InvalidOperation:
            value = Decimal(-1)
        if len(cur) != 3 or not cur.isalpha() or cur == "EUR":
            raise ValidationError({"currency": "Troslovni kod valute (osim EUR)."})
        if not value.is_finite() or value <= 0:
            raise ValidationError({"per_eur": "Tečaj mora biti pozitivan broj (jedinica za 1 EUR)."})
        self.store.put(cur, value, date.today(), "manual")
        self._invalidate()

    def remove_manual(self, currency: str) -> bool:
        ok = self.store.delete(currency.upper())
        self._invalidate()
        return ok

    def convert(self, amount: Decimal, src: str, dst: str) -> Converted:
        if src == dst:
            return Converted(amount, None)
        table = self.table()
        a, b = table.get(src), table.get(dst)
        if not a or not b:
            return Converted(None, None)
        dates = [d for d in (a["rate_date"], b["rate_date"]) if d]
        return Converted(amount / a["per_eur"] * b["per_eur"], min(dates) if dates else None)

    def listing(self) -> list[dict]:
        return [{"currency": c, "per_eur": str(v["per_eur"]), "rate_date": v["rate_date"], "source": v["source"]}
                for c, v in sorted(self.table().items())]
