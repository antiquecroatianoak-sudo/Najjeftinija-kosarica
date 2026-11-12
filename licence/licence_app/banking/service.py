"""Bank import pipeline: parse -> tokenise/mask -> deduplicate -> store -> match.

Only outgoing payments are matched. The IBAN of the statement account is
never stored (HMAC token + last 4 digits); card/account numbers inside
descriptions are masked before storage.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..models import ValidationError
from ..security import Tokenizer, mask_sensitive
from ..service import BILLED, LicenseService, NotFound
from ..repository import LicenseQuery
from ..stores import new_id
from .feeds import RawTransaction, parse_statement
from .matching import best_match, recurring_unknown


class BankService:
    def __init__(self, licenses: LicenseService, tokenizer: Tokenizer):
        self.licenses = licenses
        self.db = licenses.repo.db
        self.org = licenses.org
        self.tokenizer = tokenizer

    def _account(self, iban: str, label: str) -> str:
        token, last4 = self.tokenizer.iban(iban or "UNKNOWN")
        row = self.db.one("SELECT id FROM bank_accounts WHERE organization_id = ? AND account_token = ?",
                          (self.org.id, token))
        if row:
            return row["id"]
        aid = new_id("acc")
        self.db.execute("INSERT INTO bank_accounts (id, organization_id, account_token, last4, label) VALUES (?, ?, ?, ?, ?)",
                        (aid, self.org.id, token, last4 if iban else "????", label[:60] or f"Račun •••• {last4}"))
        return aid

    def import_statement(self, filename: str, content: bytes, label: str = "") -> dict[str, Any]:
        fmt, items = parse_statement(filename, content)
        if not items:
            raise ValidationError({"file": "U izvodu nema transakcija."})
        stats = {"format": fmt, "read": len(items), "imported": 0, "duplicates": 0,
                 "matched": 0, "suggested": 0, "unmatched": 0}
        candidates = self.licenses.repo.find(LicenseQuery(statuses=BILLED))
        with self.db.transaction():
            for tx in items:
                account_id = self._account(tx.account_iban, label)
                token, _ = self.tokenizer.iban(tx.account_iban or "UNKNOWN")
                fp = tx.fingerprint(token)
                status, match = ("unmatched", None)
                if tx.amount < 0:
                    status, match = best_match(candidates, tx.amount, tx.currency, tx.booked_on,
                                               f"{tx.counterparty} {tx.description}", self.licenses.rates.convert)
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO bank_transactions (id, organization_id, account_id, fingerprint, booked_on,"
                    " amount, currency, counterparty, description, status, license_id, match_score, match_note)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("btx"), self.org.id, account_id, fp, tx.booked_on.isoformat(), str(tx.amount), tx.currency,
                     mask_sensitive(tx.counterparty)[:120], mask_sensitive(tx.description)[:300],
                     "unmatched" if tx.amount >= 0 else status,
                     match.license_id if match else None, match.score if match else None, match.note if match else None))
                if cur.rowcount == 0:
                    stats["duplicates"] += 1
                    continue
                stats["imported"] += 1
                if tx.amount < 0:
                    stats[status] += 1
                    if status == "matched":
                        lic = next(l for l in candidates if l.id == match.license_id)
                        self.licenses.events.publish(self.org.id, "bank.matched", {
                            "license_id": lic.id, "license": lic.name, "amount": str(-tx.amount),
                            "currency": tx.currency, "booked_on": tx.booked_on.isoformat(), "score": match.score})
            self.licenses.audit.record(self.org.id, self.licenses.actor, "import", "bank_statement", None,
                                       {k: v for k, v in stats.items()})
        recurring = self.recurring()
        if recurring:
            self.licenses.events.publish(
                self.org.id, "bank.unmatched_recurring", {"items": recurring[:10]},
                notify=f"Izvod sadrži {len(recurring)} ponavljajućih plaćanja koja nisu u evidenciji licenci.",
                dedupe_key=f"recurring:{date.today():%Y-%m}:{len(recurring)}")
        stats["recurring_unknown"] = len(recurring)
        return stats

    def transactions(self, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = ("SELECT t.id, t.booked_on, t.amount, t.currency, t.counterparty, t.description, t.status,"
               " t.license_id, t.match_score, t.match_note, l.name AS license_name, a.last4"
               " FROM bank_transactions t LEFT JOIN licenses l ON l.id = t.license_id"
               " JOIN bank_accounts a ON a.id = t.account_id WHERE t.organization_id = ?")
        params: list[Any] = [self.org.id]
        if status:
            if status not in ("unmatched", "suggested", "matched", "ignored"):
                raise ValidationError({"status": "Nepoznat status transakcije."})
            sql += " AND t.status = ?"
            params.append(status)
        sql += " ORDER BY t.booked_on DESC, t.id LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def summary(self) -> dict[str, Any]:
        rows = self.db.query("SELECT status, count(*) AS n FROM bank_transactions WHERE organization_id = ?"
                             " AND CAST(amount AS REAL) < 0 GROUP BY status", (self.org.id,))
        return {r["status"]: r["n"] for r in rows}

    def recurring(self) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT booked_on, amount, currency, counterparty FROM bank_transactions"
                             " WHERE organization_id = ? AND status = 'unmatched'", (self.org.id,))
        return recurring_unknown([dict(r) for r in rows])

    def resolve(self, tx_id: str, action: str, license_id: str | None = None) -> dict[str, Any]:
        row = self.db.one("SELECT id, amount FROM bank_transactions WHERE organization_id = ? AND id = ?",
                          (self.org.id, tx_id))
        if not row:
            raise NotFound(tx_id)
        if action == "match":
            if not license_id:
                raise ValidationError({"license_id": "Odaberite licencu."})
            self.licenses.get(license_id)   # must belong to this organization
            self.db.execute("UPDATE bank_transactions SET status = 'matched', license_id = ?, match_score = 1.0,"
                            " match_note = 'ručno' WHERE id = ?", (license_id, tx_id))
        elif action == "ignore":
            self.db.execute("UPDATE bank_transactions SET status = 'ignored', license_id = NULL WHERE id = ?", (tx_id,))
        elif action == "reset":
            self.db.execute("UPDATE bank_transactions SET status = 'unmatched', license_id = NULL, match_score = NULL,"
                            " match_note = NULL WHERE id = ?", (tx_id,))
        else:
            raise ValidationError({"action": "Dopušteno: match, ignore, reset."})
        self.licenses.audit.record(self.org.id, self.licenses.actor, f"bank_{action}", "bank_transaction", tx_id,
                                   {"license_id": license_id})
        return dict(self.db.one("SELECT id, status, license_id FROM bank_transactions WHERE id = ?", (tx_id,)))

    def price_drift(self) -> list[dict[str, Any]]:
        """Matched payments whose amount differs from the registered cost by > 2 % (same currency)."""
        rows = self.db.query(
            "SELECT t.booked_on, t.amount, t.currency, l.id, l.name, l.cost, l.currency AS lcur FROM bank_transactions t"
            " JOIN licenses l ON l.id = t.license_id WHERE t.organization_id = ? AND t.status = 'matched'"
            " ORDER BY t.booked_on DESC", (self.org.id,))
        seen, out = set(), []
        for r in rows:
            if r["id"] in seen or r["currency"] != r["lcur"]:
                continue
            seen.add(r["id"])
            paid, cost = -Decimal(r["amount"]), Decimal(r["cost"])
            if cost > 0 and abs(paid / cost - 1) > Decimal("0.02") and abs(paid / cost - Decimal("1.25")) > Decimal("0.01"):
                out.append({"license_id": r["id"], "name": r["name"], "registered": str(cost), "paid": str(paid),
                            "currency": r["currency"], "booked_on": r["booked_on"]})
        return out
