"""Protocol for live bank connections (PSD2 Account Information Service).

Not implemented against a real bank: a live connection requires a regulated
AISP (own licence or a provider such as an open-banking aggregator), a
contract, and per-customer consent. This module fixes the contract so a
provider adapter can be added without touching matching or storage.

Phases (see docs/BANKING.md):
1. authorize  - redirect the admin to the bank/aggregator consent page
                (OAuth2 authorization code + PKCE, state bound to the org).
2. exchange   - exchange the code for tokens; store only an encrypted refresh
                token / consent id with its expiry (max 180 days under PSD2 SCA).
3. sync       - fetch booked transactions since the last cursor (read-only
                scope), normalise to RawTransaction, then the same pipeline as
                file imports: tokenise -> deduplicate -> store -> match.
4. renew      - before consent expiry, notify the admin to re-authorise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from .feeds import RawTransaction


class ConnectorNotConfigured(RuntimeError):
    """No live bank provider is configured; use statement import instead."""


@dataclass(frozen=True)
class Consent:
    consent_id: str
    expires_at: datetime
    accounts: tuple[str, ...]       # provider account ids, never IBANs in logs


@dataclass(frozen=True)
class SyncResult:
    transactions: list[RawTransaction]
    cursor: str | None              # opaque position for the next incremental sync


class BankConnector(Protocol):
    name: str

    def authorize_url(self, organization_id: str, state: str, redirect_uri: str, code_verifier: str) -> str:
        """Phase 1: URL of the consent page."""

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> Consent:
        """Phase 2: complete consent; the caller stores the returned secret material encrypted."""

    def fetch(self, consent: Consent, since: date | None, cursor: str | None) -> SyncResult:
        """Phase 3: booked transactions (read-only)."""


def get_connector(name: str | None) -> BankConnector:
    raise ConnectorNotConfigured(
        "Živa veza s bankom nije konfigurirana. Uvezite izvod (camt.053 ili CSV) iz internetskog bankarstva.")
