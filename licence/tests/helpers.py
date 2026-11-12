"""Shared test fixtures: an App on an in-memory or file database, fake
network (ECB feed, webhook sender), users and an HTTP client."""
from __future__ import annotations

import base64
import http.client
import json
import threading
from datetime import date
from pathlib import Path

from licence_app.api import create_server
from licence_app.app import App
from licence_app.config import load_settings
from licence_app.webhooks import resolve_public

TODAY = date(2026, 11, 12)
WEB = Path(__file__).resolve().parent.parent / "web"
PASSWORD = "dovoljno-duga-lozinka-1"

ECB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <Cube><Cube time="2026-11-11">
    <Cube currency="USD" rate="1.0800"/><Cube currency="GBP" rate="0.8400"/><Cube currency="CHF" rate="0.9500"/>
  </Cube></Cube>
</gesmes:Envelope>"""


def license_data(**over):
    base = {"name": "App", "category": "Razvoj", "cost": "10", "currency": "EUR",
            "billing_cycle": "monthly", "start_date": "2025-01-01", "status": "active"}
    return {**base, **over}


class FakeSender:
    def __init__(self, status: int = 200):
        self.status, self.calls = status, []

    def __call__(self, url, secret, event, delivery_id, body, allow_private):
        self.calls.append({"url": url, "event": event, "body": json.loads(body)})
        if isinstance(self.status, Exception):
            raise self.status
        return self.status


def fake_resolve(host: str, port: int, allow_private: bool) -> str:
    """Offline DNS: example domains resolve to a public documentation-free address;
    IP literals and localhost go through the real SSRF check."""
    if host.endswith(("example.com", "example.org")):
        return "93.184.215.14"
    return resolve_public(host, port, allow_private)


def make_app(db_path: str = ":memory:", *, today=TODAY, sender=None, env=None) -> App:
    settings = load_settings(env or {}, db_path=db_path, secret_key="k" * 40, maintenance=False)
    return App(settings, today=lambda: today, rate_fetch=lambda url: ECB_XML,
               webhook_sender=sender or FakeSender(), webhook_resolve=fake_resolve)


def org_with_admin(app: App, slug: str = "acme", username: str = "ana"):
    org = app.create_organization(f"{slug.title()} d.o.o.", slug)
    user = app.create_user(org.id, username, PASSWORD, "admin")
    return org, user


def basic(username: str, password: str = PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


class Running:
    """App served over HTTP on a random port."""

    def __init__(self, app: App):
        self.app = app
        self.server = create_server(app, port=0, static_dir=WEB)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, method, path, body=None, *, user="ana", password=PASSWORD, auth=None, raw=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        hdrs = {}
        if data:
            hdrs["Content-Type"] = "application/json"
        if auth is not None:
            if auth:
                hdrs["Authorization"] = auth
        elif user:
            hdrs["Authorization"] = basic(user, password)
        if method not in ("GET", "HEAD"):
            hdrs["X-Requested-With"] = "LicensePulse"
        hdrs.update(headers or {})
        hdrs = {k: v for k, v in hdrs.items() if v is not None}
        conn.request(method, path, body=data, headers=hdrs)
        res = conn.getresponse()
        payload = res.read()
        out_headers = {k.lower(): v for k, v in res.getheaders()}
        conn.close()
        if "json" in out_headers.get("content-type", ""):
            payload = json.loads(payload)
        return res.status, payload, out_headers
