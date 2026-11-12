"""Credentials and sensitive-data handling (stdlib only).

- Passwords: PBKDF2-HMAC-SHA256, per-user salt, constant-time compare.
- HTTP Basic sends the password with every request, so successful checks are
  cached in memory for a few minutes (keyed by a hash, never the password).
- Failed logins are rate limited per client address and per username.
- API tokens: random 32 bytes shown once; only SHA-256 is stored.
- Tokenisation: IBANs and user identifiers are replaced by keyed HMACs, so the
  database never holds them in clear text.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from dataclasses import dataclass

PBKDF2_ITERATIONS = 310_000
_SCHEME = "pbkdf2_sha256"


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_SCHEME}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != _SCHEME:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# A real hash to compare against when the username does not exist, so the
# response time does not reveal which usernames are valid.
_DUMMY_HASH = hash_password(secrets.token_hex(8), iterations=PBKDF2_ITERATIONS)


def dummy_verify(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def password_problem(password: str) -> str | None:
    if len(password) < 12:
        return "Lozinka mora imati najmanje 12 znakova."
    if len(set(password)) < 5:
        return "Lozinka je prejednostavna."
    return None


class VerifiedCache:
    """Remembers successful (username, password) checks for `ttl` seconds."""

    def __init__(self, ttl: float = 300):
        self.ttl = ttl
        self._items: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(username: str, password: str, stored_hash: str) -> str:
        return hashlib.sha256(f"{username}\0{password}\0{stored_hash}".encode()).hexdigest()

    def hit(self, username: str, password: str, stored_hash: str) -> bool:
        key = self._key(username, password, stored_hash)
        with self._lock:
            item = self._items.get(key)
            return bool(item and item[0] > time.monotonic())

    def add(self, username: str, password: str, stored_hash: str) -> None:
        key = self._key(username, password, stored_hash)
        with self._lock:
            if len(self._items) > 10_000:
                self._items.clear()
            self._items[key] = (time.monotonic() + self.ttl, username)

    def forget_user(self, username: str) -> None:
        with self._lock:
            for key in [k for k, (_, u) in self._items.items() if u.casefold() == username.casefold()]:
                del self._items[key]


class LoginLimiter:
    """From the `free`-th failure on, each failure locks for base x 2^n seconds (max 15 min)."""

    def __init__(self, free: int = 5, base_seconds: float = 2.0, max_seconds: float = 900.0):
        self.free, self.base, self.max = free, base_seconds, max_seconds
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, *keys: str) -> float:
        now = time.monotonic()
        with self._lock:
            return max([0.0, *(until - now for _, until in (self._state.get(k, (0, 0.0)) for k in keys))])

    def failed(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._state) > 50_000:
                self._state.clear()
            for key in keys:
                count, _ = self._state.get(key, (0, 0.0))
                count += 1
                wait = 0.0 if count < self.free else min(self.base * 2 ** (count - self.free), self.max)
                self._state[key] = (count, now + wait)

    def succeeded(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._state.pop(key, None)


def parse_basic(header: str | None) -> tuple[str, str] | None:
    if not header or not header.startswith("Basic "):
        return None
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    username, sep, password = raw.partition(":")
    return (username, password) if sep and username else None


def parse_bearer(header: str | None) -> str | None:
    if header and header.startswith("Bearer "):
        token = header[7:].strip()
        return token or None
    return None


# --- tokens & tokenisation ------------------------------------------------------

TOKEN_PREFIX = "lp_"


def new_api_token() -> tuple[str, str]:
    """Returns (plain token shown once, hash to store)."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Tokenizer:
    """Keyed, deterministic tokens: equal inputs map to equal tokens (so we can
    deduplicate and match), but the input cannot be recovered without the key."""
    key: str

    def token(self, purpose: str, value: str) -> str:
        msg = f"{purpose}\0{value}".encode()
        return hmac.new(self.key.encode(), msg, hashlib.sha256).hexdigest()[:40]

    def iban(self, iban: str) -> tuple[str, str]:
        normalized = re.sub(r"\s", "", iban).upper()
        return self.token("iban", normalized), normalized[-4:]

    def user(self, identifier: str) -> str:
        return self.token("user", identifier.strip().casefold())


_LONG_DIGITS = re.compile(r"(?<![\w])(?:\d[ -]?){12,19}(?![\w])")
_IBAN_IN_TEXT = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b")


def mask_sensitive(text: str) -> str:
    """Mask card/account numbers in free text (statement descriptions)."""
    def mask(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "•••• " + digits[-4:]
    text = _IBAN_IN_TEXT.sub(lambda m: "IBAN •••• " + re.sub(r"\s", "", m.group(0))[-4:], text)
    return _LONG_DIGITS.sub(mask, text)
