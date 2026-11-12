"""Outgoing webhooks: validation, signing and delivery with retries.

Security
- Only https URLs (http only when private targets are explicitly allowed for
  development). The host is resolved and every address must be public
  (blocks SSRF to localhost, private networks and cloud metadata), and the
  connection is pinned to the checked address (no DNS-rebinding window).
- Redirects are not followed.
- Each request is signed: X-LicensePulse-Signature = "sha256=" +
  HMAC_SHA256(secret, f"{timestamp}.{body}"). Receivers should reject stale
  timestamps (> 5 min) and compare signatures in constant time.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import logging
import secrets
import socket
import ssl
import time
from typing import Any, Callable
from urllib.parse import urlsplit

from .events import EVENTS
from .models import ValidationError
from .stores import WebhookStore

log = logging.getLogger("licence.webhooks")
RETRY_SCHEDULE = (60, 300, 1800, 7200, 21600)   # then: failed
TIMEOUT = 8


def resolve_public(host: str, port: int, allow_private: bool) -> str:
    """Return one address for host; raise ValueError if any address is not public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Adresa se ne može razriješiti.") from None
    addresses = [info[4][0] for info in infos]
    if not allow_private:
        for addr in addresses:
            ip = ipaddress.ip_address(addr.split("%")[0])
            if not ip.is_global or ip.is_multicast:
                raise ValueError("Webhook ne smije ciljati privatnu ili lokalnu adresu.")
    return addresses[0]


def validate_url(url: str, allow_private: bool, resolve: Callable[[str, int, bool], str] = resolve_public) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ValidationError({"url": "Potrebna je potpuna adresa (https://...)."})
    if parts.scheme == "http" and not allow_private:
        raise ValidationError({"url": "Dopušten je samo https."})
    if parts.username or parts.password:
        raise ValidationError({"url": "Adresa ne smije sadržavati korisničko ime ili lozinku."})
    if len(url) > 500:
        raise ValidationError({"url": "Adresa je predugačka."})
    try:
        resolve(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), allow_private)
    except ValueError as e:
        raise ValidationError({"url": str(e)}) from None
    return url.strip()


def validate_events(events: Any) -> str:
    if events in (None, "", "*", ["*"]):
        return "*"
    if not isinstance(events, list) or not all(isinstance(e, str) for e in events):
        raise ValidationError({"events": "Popis događaja ili '*'."})
    unknown = [e for e in events if e not in EVENTS]
    if unknown:
        raise ValidationError({"events": f"Nepoznati događaji: {', '.join(unknown)}"})
    return ",".join(sorted(set(events)))


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class _Pinned(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, port: int):
        super().__init__(host, port, timeout=TIMEOUT, context=ssl.create_default_context())
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedPlain(http.client.HTTPConnection):
    def __init__(self, host: str, ip: str, port: int):
        super().__init__(host, port, timeout=TIMEOUT)
        self._ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


def post(url: str, secret: str, event: str, delivery_id: str, body: bytes, allow_private: bool) -> int:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    ip = resolve_public(parts.hostname, port, allow_private)
    conn_cls = _Pinned if parts.scheme == "https" else _PinnedPlain
    conn = conn_cls(parts.hostname, ip, port)
    ts = str(int(time.time()))
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    try:
        conn.request("POST", path, body=body, headers={
            "Content-Type": "application/json", "User-Agent": "LicensePulse-Webhook/1.0",
            "X-LicensePulse-Event": event, "X-LicensePulse-Delivery": delivery_id,
            "X-LicensePulse-Timestamp": ts, "X-LicensePulse-Signature": sign(secret, ts, body)})
        res = conn.getresponse()
        res.read(4096)
        return res.status
    finally:
        conn.close()


class WebhookService:
    def __init__(self, store: WebhookStore, allow_private: bool,
                 sender: Callable[..., int] = post, resolve: Callable[[str, int, bool], str] = resolve_public):
        self.store, self.allow_private, self.sender, self.resolve = store, allow_private, sender, resolve

    def create(self, org_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError({"_": "Očekuje se JSON objekt."})
        url = validate_url(str(data.get("url") or ""), self.allow_private, self.resolve)
        events = validate_events(data.get("events"))
        secret = "whsec_" + secrets.token_urlsafe(32)
        hook = self.store.create(org_id, url, secret, events)
        return {**hook, "secret": secret}   # the secret is shown only once

    def deliver_due(self, limit: int = 20) -> dict[str, int]:
        stats = {"sent": 0, "retry": 0, "failed": 0}
        for d in self.store.due(limit):
            attempts = d["attempts"] + 1
            try:
                status = self.sender(d["url"], d["secret"], d["event"], str(d["id"]), d["payload"].encode(),
                                     self.allow_private)
                error = None if 200 <= status < 300 else f"HTTP {status}"
            except Exception as e:  # network errors, TLS, DNS, SSRF guard
                status, error = None, f"{type(e).__name__}: {e}"[:300]
            if error is None:
                self.store.mark(d["id"], "sent", attempts, response_status=status)
                stats["sent"] += 1
            elif attempts > len(RETRY_SCHEDULE):
                self.store.mark(d["id"], "failed", attempts, error=error, response_status=status)
                stats["failed"] += 1
                log.warning("webhook_failed", extra={"fields": {"webhook": d["webhook_id"], "event": d["event"], "error": error}})
            else:
                self.store.mark(d["id"], "pending", attempts, error=error, response_status=status,
                                retry_in_seconds=RETRY_SCHEDULE[attempts - 1])
                stats["retry"] += 1
        return stats
