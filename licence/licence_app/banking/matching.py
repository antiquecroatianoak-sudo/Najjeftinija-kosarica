"""Matching bank transactions to licenses (deterministic scoring, no ML).

Score (0..1) for an outgoing transaction vs a billed license:
- amount   0.45  exact (±1 %), 0.30 same amount plus Croatian VAT 25 % / 13 %,
                 0.20 within 10 % (price change or FX), converted via rates if
                 currencies differ
- name     0.35  license name / usage_key words found in counterparty+description
- date     0.20  booked within ±5 days of a scheduled charge (±10 days: 0.10)
Auto-match: best score >= 0.70 and ahead of the runner-up by >= 0.15.
Suggestion: best score >= 0.40. Everything else stays unmatched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from ..models import License
from ..service import charges_between
from ..transfer import fold

AUTO, SUGGEST, MARGIN = 0.70, 0.40, 0.15
_STOP = {"pro", "plus", "team", "teams", "business", "standard", "professional", "enterprise", "basic",
         "premium", "cloud", "app", "the", "and", "for", "inc", "ltd", "llc", "d", "o", "doo", "plan"}


@dataclass(frozen=True)
class Match:
    license_id: str
    score: float
    note: str


def _words(text: str) -> set[str]:
    return {w for w in fold(text).split() if len(w) >= 3 and w not in _STOP}


def amount_score(paid: Decimal, expected: Decimal) -> tuple[float, str]:
    if expected <= 0:
        return 0.0, ""
    ratio = paid / expected
    if abs(ratio - 1) <= Decimal("0.01"):
        return 0.45, "iznos"
    for vat in (Decimal("1.25"), Decimal("1.13")):
        if abs(ratio - vat) <= Decimal("0.01"):
            return 0.30, f"iznos + PDV {int((vat - 1) * 100)} %"
    if abs(ratio - 1) <= Decimal("0.10"):
        return 0.20, "približan iznos"
    return 0.0, ""


def name_score(lic: License, text_words: set[str]) -> tuple[float, str]:
    words = _words(lic.name) | (_words(lic.usage_key.replace(".", " ").replace("-", " ")) if lic.usage_key else set())
    if not words:
        return 0.0, ""
    hits = words & text_words
    if not hits:
        # also accept prefixes ("ADOBE *CREATIVE" vs "adobe")
        hits = {w for w in words if any(t.startswith(w) or w.startswith(t) for t in text_words if len(t) >= 4)}
    if not hits:
        return 0.0, ""
    return (0.35 if len(hits) >= min(2, len(words)) else 0.25), "naziv"


def date_score(lic: License, booked: date) -> tuple[float, str]:
    near = charges_between(lic, booked - timedelta(days=10), booked + timedelta(days=10))
    if not near:
        return 0.0, ""
    gap = min(abs((d - booked).days) for d in near)
    if gap <= 5:
        return 0.20, "datum naplate"
    return 0.10, "blizu datuma naplate"


def score(lic: License, amount: Decimal, currency: str, booked: date, text: str,
          convert=None) -> Match | None:
    paid = -amount
    if paid <= 0:
        return None
    expected = lic.cost
    if currency != lic.currency:
        if convert is None:
            return None
        conv = convert(lic.cost, lic.currency, currency)
        if conv.amount is None:
            return None
        expected = conv.amount
    parts = [amount_score(paid, expected), name_score(lic, _words(text)), date_score(lic, booked)]
    total = round(sum(p[0] for p in parts), 2)
    note = ", ".join(p[1] for p in parts if p[1])
    return Match(lic.id, total, note) if total > 0 else None


def best_match(licenses: list[License], amount: Decimal, currency: str, booked: date, text: str,
               convert=None) -> tuple[str, Match | None]:
    """Returns ('matched' | 'suggested' | 'unmatched', best match)."""
    scored = sorted((m for l in licenses if (m := score(l, amount, currency, booked, text, convert))),
                    key=lambda m: -m.score)
    if not scored or scored[0].score < SUGGEST:
        return "unmatched", None
    top = scored[0]
    runner = scored[1].score if len(scored) > 1 else 0.0
    if top.score >= AUTO and top.score - runner >= MARGIN:
        return "matched", top
    return "suggested", top


def recurring_unknown(rows: list[dict]) -> list[dict]:
    """Unmatched outgoing payments to the same counterparty in >= 2 different
    months with similar amounts: probably a subscription nobody registered."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if Decimal(r["amount"]) >= 0:
            continue
        key = " ".join(sorted(_words(r["counterparty"]))) or fold(r["counterparty"])
        if key:
            groups.setdefault(key, []).append(r)
    out = []
    for key, items in groups.items():
        months = {r["booked_on"][:7] for r in items}
        amounts = [abs(Decimal(r["amount"])) for r in items]
        if len(months) >= 2 and max(amounts) <= min(amounts) * Decimal("1.15"):
            latest = max(items, key=lambda r: r["booked_on"])
            out.append({"counterparty": latest["counterparty"], "months": len(months),
                        "amount": str(abs(Decimal(latest["amount"]))), "currency": latest["currency"],
                        "last_booked_on": latest["booked_on"]})
    return sorted(out, key=lambda r: -Decimal(r["amount"]))
