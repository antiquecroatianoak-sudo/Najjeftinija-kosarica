"""Bank statement feeds -> normalised transactions.

Supported now (no third party, no credentials):
- ISO 20022 camt.053 (bank-to-customer statement, XML) - exported by most
  European banks, including Croatian ones, from online banking.
- CSV statements: columns detected by header names (date, amount or
  debit/credit, currency, counterparty/payee, description).

Live bank APIs plug in through banking.connector.BankConnector and produce
the same RawTransaction objects.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from ..models import ValidationError
from ..transfer import _decode, fold, norm_cost, norm_date
from ..xmlsafe import UnsafeXML, fromstring, local

MAX_STATEMENT = 10 * 1024 * 1024


@dataclass(frozen=True)
class RawTransaction:
    account_iban: str          # statement account (tokenised before storage)
    booked_on: date
    amount: Decimal            # negative = money out
    currency: str
    counterparty: str
    description: str
    reference: str = ""        # bank's own id when present (dedupe)

    def fingerprint(self, account_token: str) -> str:
        basis = self.reference or f"{self.booked_on}|{self.amount}|{self.currency}|{self.counterparty}|{self.description}"
        return hashlib.sha256(f"{account_token}|{basis}".encode()).hexdigest()[:40]


def parse_statement(filename: str, content: bytes, default_iban: str = "") -> tuple[str, list[RawTransaction]]:
    if len(content) > MAX_STATEMENT:
        raise ValidationError({"file": "Izvod je veći od 10 MB."})
    head = content[:2048].lstrip()
    if head.startswith(b"<") or (filename or "").lower().endswith(".xml"):
        return "camt.053", parse_camt053(content)
    return "csv", parse_csv(content, default_iban)


def _text(el, *path: str) -> str:
    """First descendant following the local-name path, e.g. _text(x, 'Acct', 'Id', 'IBAN')."""
    nodes = [el]
    for name in path:
        nodes = [c for n in nodes for c in n.iter() if c is not n and local(c.tag) == name][:1]
        if not nodes:
            return ""
    return (nodes[0].text or "").strip()


def parse_camt053(content: bytes) -> list[RawTransaction]:
    try:
        root = fromstring(content, MAX_STATEMENT)
    except UnsafeXML as e:
        raise ValidationError({"file": str(e)}) from None
    out: list[RawTransaction] = []
    statements = [s for s in root.iter() if local(s.tag) == "Stmt"]
    if not statements:
        raise ValidationError({"file": "Nije camt.053 izvod (nema elementa Stmt)."})
    for stmt in statements:
        iban = _text(stmt, "Acct", "IBAN")
        for ntry in (e for e in stmt.iter() if local(e.tag) == "Ntry"):
            amt_el = next((c for c in ntry if local(c.tag) == "Amt"), None)
            if amt_el is None:
                continue
            try:
                amount = Decimal((amt_el.text or "").strip())
            except InvalidOperation:
                continue
            if _text(ntry, "CdtDbtInd") == "DBIT":
                amount = -amount
            booked = _text(ntry, "BookgDt", "Dt") or _text(ntry, "BookgDt", "DtTm")[:10] or _text(ntry, "ValDt", "Dt")
            try:
                booked_on = date.fromisoformat(booked[:10])
            except ValueError:
                continue
            # counterparty: creditor for payments out, debtor for money in
            party = _text(ntry, "RltdPties", "Cdtr", "Nm") if amount < 0 else _text(ntry, "RltdPties", "Dbtr", "Nm")
            info = " ".join(filter(None, [_text(ntry, "RmtInf", "Ustrd"), _text(ntry, "AddtlNtryInf")]))
            ref = _text(ntry, "AcctSvcrRef") or _text(ntry, "NtryRef")
            out.append(RawTransaction(iban, booked_on, amount, amt_el.attrib.get("Ccy", "EUR").upper(),
                                      party or info[:60], info, ref))
    return out


_COLS = {
    "date": ["datum knjizenja", "datum izvrsenja", "datum valute", "datum", "date", "booking date", "value date", "posted"],
    "amount": ["iznos", "amount", "value"],
    "debit": ["isplata", "terecenje", "debit", "zaduzenje", "out"],
    "credit": ["uplata", "odobrenje", "credit", "in"],
    "currency": ["valuta", "currency", "ccy"],
    "party": ["primatelj", "platitelj", "naziv", "counterparty", "payee", "merchant", "beneficiary", "partner"],
    "description": ["opis", "svrha", "description", "details", "memo", "narrative", "opis placanja"],
    "reference": ["referenca", "reference", "id", "transaction id", "poziv na broj"],
    "iban": ["iban", "racun", "account"],
}


def _find(headers: list[str], key: str) -> int | None:
    folded = [fold(h) for h in headers]
    for syn in _COLS[key]:
        for i, h in enumerate(folded):
            if h == syn or h.startswith(syn + " "):
                return i
    return None


def parse_csv(content: bytes, default_iban: str = "") -> list[RawTransaction]:
    import csv
    import io
    text = _decode(content)
    sample = text[:4096]
    delim = max(";,\t", key=sample.count)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValidationError({"file": "CSV izvod nema transakcija."})
    headers = rows[0]
    idx = {k: _find(headers, k) for k in _COLS}
    if idx["date"] is None or (idx["amount"] is None and idx["debit"] is None):
        raise ValidationError({"file": "CSV izvod mora imati stupce za datum i iznos (ili isplatu/uplatu)."})
    get = lambda r, k: r[idx[k]].strip() if idx[k] is not None and idx[k] < len(r) else ""
    out = []
    for r in rows[1:]:
        try:
            booked_on = date.fromisoformat(norm_date(get(r, "date")))
            if idx["amount"] is not None and get(r, "amount"):
                amount = Decimal(norm_cost(get(r, "amount")))
            else:
                debit = Decimal(norm_cost(get(r, "debit")) or 0)
                credit = Decimal(norm_cost(get(r, "credit")) or 0)
                amount = credit - abs(debit)
        except (ValueError, InvalidOperation):
            continue  # summary/footer lines
        cur = (get(r, "currency") or "EUR").upper()[:3]
        iban = re.sub(r"\s", "", get(r, "iban")) or default_iban
        out.append(RawTransaction(iban, booked_on, amount, cur, get(r, "party") or get(r, "description")[:60],
                                  get(r, "description"), get(r, "reference")))
    return out
