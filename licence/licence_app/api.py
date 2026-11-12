"""HTTP layer: JSON REST API + static UI on the standard library server.

Security per request
- Authentication: HTTP Basic (users) on every route except /api/health and
  static assets; Bearer API tokens only on POST /api/usage.
- CSRF: state-changing requests must carry `X-Requested-With: LicensePulse`
  (a cross-site page cannot add it without a CORS preflight, which is never
  granted) and, when present, a same-origin `Origin`.
- Tenant isolation: every handler gets a workspace bound to the caller's
  organization; ids from other organizations simply are not found.
- Security headers on every response; request id in logs and responses.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import mimetypes
import re
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

from .app import App, AuthError, Principal, Workspace
from .banking.connector import ConnectorNotConfigured
from .events import EVENTS
from .models import BillingCycle, LicenseStatus, ValidationError
from .security import new_api_token
from .service import LicenseFilter, NotFound, parse_window
from .transfer import commit as import_commit, export_csv, preview as import_preview

log = logging.getLogger("licence.http")

MAX_BODY = 64 * 1024
MAX_UPLOAD_BODY = 14 * 1024 * 1024
_ID = r"(?P<id>[0-9a-f]{32})"
_PID = r"(?P<id>[a-z]{3}_[0-9a-f]{32})"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
    ),
}
PUBLIC_STATIC = re.compile(r"^/(css|js|img)/[\w./-]+$")


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    body: bytes
    params: dict[str, str]
    principal: Principal | None = None
    ws: Workspace | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        if not self.body:
            raise ApiError(HTTPStatus.BAD_REQUEST, "empty_body", "Nedostaje JSON tijelo zahtjeva.")
        try:
            return json.loads(self.body)
        except (ValueError, UnicodeDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json", "Neispravan JSON.") from None

    def upload(self) -> tuple[dict, str, bytes]:
        data = self.json()
        if not isinstance(data, dict):
            raise ValidationError({"_": "Očekuje se JSON objekt."})
        try:
            content = base64.b64decode(str(data.get("content_base64") or ""), validate=True)
        except (binascii.Error, ValueError):
            raise ValidationError({"file": "Datoteka mora biti base64."}) from None
        if not content:
            raise ValidationError({"file": "Datoteka je prazna."})
        return data, str(data.get("filename") or "")[:200], content


Handler = Callable[[Request], tuple[int, Any]]


@dataclass
class Route:
    method: str
    pattern: re.Pattern
    handler: Handler
    auth: str = "user"          # user | token_or_user | none
    admin: bool = False
    max_body: int = MAX_BODY


class Router:
    def __init__(self) -> None:
        self.routes: list[Route] = []

    def add(self, method: str, pattern: str, handler: Handler, **opts) -> None:
        self.routes.append(Route(method, re.compile(f"^{pattern}$"), handler, **opts))

    def resolve(self, method: str, path: str) -> tuple[Route, dict[str, str]]:
        known = False
        for r in self.routes:
            m = r.pattern.match(path)
            if m:
                known = True
                if r.method == method:
                    return r, m.groupdict()
        if known:
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Metoda nije dopuštena.")
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")


def _ok(data: Any) -> tuple[int, Any]:
    return 200, data


def build_router(app: App, scheduler=None) -> Router:
    r = Router()
    L = lambda req: req.ws.licenses

    # --- session & organization ---------------------------------------------
    r.add("GET", "/api/health", lambda req: _ok({"status": "ok"}), auth="none")
    r.add("GET", "/api/me", lambda req: _ok({
        "user": req.principal.user.to_dict(), "organization": req.ws.org.to_dict(),
        "billing_cycles": [c.value for c in BillingCycle], "statuses": [s.value for s in LicenseStatus],
        "categories": L(req).categories(), "events": list(EVENTS)}))
    r.add("PATCH", "/api/organization",
          lambda req: _ok(app.update_organization(req.principal, req.json()).to_dict()), admin=True)

    def change_password(req):
        data = req.json()
        app.change_password(req.principal, str(data.get("current") or ""), str(data.get("password") or ""))
        return 204, None
    r.add("POST", "/api/me/password", change_password)

    # --- users & tokens (admin) ------------------------------------------------
    r.add("GET", "/api/users", lambda req: _ok({"items": [u.to_dict() for u in app.users.list(req.ws.org.id)]}), admin=True)

    def create_user(req):
        d = req.json()
        user = app.create_user(req.ws.org.id, str(d.get("username") or "").strip(), str(d.get("password") or ""),
                               str(d.get("role") or "member"))
        app.audit.record(req.ws.org.id, req.principal.actor, "create", "user", user.id, {"username": user.username})
        return 201, user.to_dict()
    r.add("POST", "/api/users", create_user, admin=True)

    def delete_user(req):
        uid = req.params["id"]
        target = next((u for u in app.users.list(req.ws.org.id) if u.id == uid), None)
        if target is None:
            raise NotFound(uid)
        if target.id == req.principal.user.id:
            raise ValidationError({"_": "Ne možete obrisati vlastiti račun."})
        if target.is_admin and app.users.admins(req.ws.org.id) <= 1:
            raise ValidationError({"_": "Organizacija mora imati barem jednog administratora."})
        app.users.delete(req.ws.org.id, uid)
        app.verified.forget_user(target.username)
        app.audit.record(req.ws.org.id, req.principal.actor, "delete", "user", uid, {"username": target.username})
        return 204, None
    r.add("DELETE", f"/api/users/{_PID}", delete_user, admin=True)

    r.add("GET", "/api/tokens", lambda req: _ok({"items": app.tokens.list(req.ws.org.id)}), admin=True)

    def create_token(req):
        name = str(req.json().get("name") or "").strip()[:60]
        if not name:
            raise ValidationError({"name": "Upišite naziv tokena (npr. Okta)."})
        plain, hashed = new_api_token()
        meta = app.tokens.create(req.ws.org.id, name, hashed)
        app.audit.record(req.ws.org.id, req.principal.actor, "create", "api_token", meta["id"], {"name": name})
        return 201, {**meta, "token": plain}    # shown once
    r.add("POST", "/api/tokens", create_token, admin=True)

    def delete_token(req):
        if not app.tokens.delete(req.ws.org.id, req.params["id"]):
            raise NotFound(req.params["id"])
        app.audit.record(req.ws.org.id, req.principal.actor, "delete", "api_token", req.params["id"])
        return 204, None
    r.add("DELETE", f"/api/tokens/{_PID}", delete_token, admin=True)

    # --- licenses -----------------------------------------------------------------
    r.add("GET", "/api/licenses", lambda req: _ok({
        "items": L(req).view(L(req).list(LicenseFilter.from_params(req.query)))}))
    r.add("POST", "/api/licenses", lambda req: (201, L(req).view([L(req).create(req.json())])[0]))
    r.add("GET", f"/api/licenses/{_ID}", lambda req: _ok(L(req).view([L(req).get(req.params["id"])])[0]))
    r.add("PUT", f"/api/licenses/{_ID}",
          lambda req: _ok(L(req).view([L(req).replace(req.params["id"], req.json())])[0]))
    r.add("PATCH", f"/api/licenses/{_ID}",
          lambda req: _ok(L(req).view([L(req).patch(req.params["id"], req.json())])[0]))

    def delete_license(req):
        L(req).delete(req.params["id"])
        return 204, None
    r.add("DELETE", f"/api/licenses/{_ID}", delete_license)

    r.add("GET", "/api/dashboard", lambda req: _ok({
        **L(req).dashboard(parse_window(req.query.get("days"))),
        "unread_notifications": app.notifications.unread(req.ws.org.id)}))
    r.add("GET", "/api/analytics", lambda req: _ok(L(req).analytics()))

    # --- import / export ----------------------------------------------------------
    def export(req):
        body = export_csv(L(req).view(L(req).list(LicenseFilter.from_params(req.query))))
        req.extra_headers.update({
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="licence-{req.ws.org.slug}-{app.today():%Y-%m-%d}.csv"'})
        return 200, body
    r.add("GET", "/api/export.csv", export)

    def preview(req):
        _, name, content = req.upload()
        return _ok(import_preview(name, content))
    r.add("POST", "/api/import/preview", preview, max_body=MAX_UPLOAD_BODY)

    def commit(req):
        data, name, content = req.upload()
        result = import_commit(L(req), name, content, data.get("mapping"), data.get("defaults"),
                               skip_invalid=bool(data.get("skip_invalid")),
                               skip_duplicates=data.get("skip_duplicates", True) is not False)
        return (201 if result["committed"] else 422), result
    r.add("POST", "/api/import/commit", commit, max_body=MAX_UPLOAD_BODY)

    # --- usage tracking -------------------------------------------------------------
    r.add("POST", "/api/usage", lambda req: (202, req.ws.usage.ingest(
        req.json(), source="token" if req.principal.user is None else "ui")), auth="token_or_user", max_body=512 * 1024)

    # --- exchange rates -------------------------------------------------------------
    r.add("GET", "/api/rates", lambda req: _ok({"items": app.rates.listing(), "last_fetch": app.rates.store.last_fetch(),
                                                "auto": app.settings.rates_auto}))

    def put_rate(req):
        app.rates.set_manual(req.params["cur"], req.json().get("per_eur"))
        app.audit.record(req.ws.org.id, req.principal.actor, "set_rate", "exchange_rate", req.params["cur"])
        return _ok({"items": app.rates.listing()})
    r.add("PUT", r"/api/rates/(?P<cur>[A-Z]{3})", put_rate, admin=True)

    def delete_rate(req):
        if not app.rates.remove_manual(req.params["cur"]):
            raise NotFound(req.params["cur"])
        return 204, None
    r.add("DELETE", r"/api/rates/(?P<cur>[A-Z]{3})", delete_rate, admin=True)

    def refresh_rates(req):
        try:
            return _ok(app.rates.refresh())
        except Exception as e:
            raise ApiError(HTTPStatus.BAD_GATEWAY, "rates_unavailable",
                           f"Tečajna lista trenutačno nije dostupna ({type(e).__name__}).") from None
    r.add("POST", "/api/rates/refresh", refresh_rates, admin=True)

    # --- notifications & webhooks -----------------------------------------------------
    r.add("GET", "/api/notifications", lambda req: _ok({
        "items": app.notifications.list(req.ws.org.id), "unread": app.notifications.unread(req.ws.org.id)}))

    def read_notifications(req):
        ids = req.json().get("ids") if req.body else None
        if ids is not None and (not isinstance(ids, list) or not all(isinstance(i, int) for i in ids)):
            raise ValidationError({"ids": "Popis brojeva."})
        return _ok({"marked": app.notifications.mark_read(req.ws.org.id, ids)})
    r.add("POST", "/api/notifications/read", read_notifications)

    r.add("GET", "/api/webhooks", lambda req: _ok({"items": app.webhook_store.list(req.ws.org.id), "events": list(EVENTS)}),
          admin=True)

    def create_webhook(req):
        hook = app.webhooks.create(req.ws.org.id, req.json())
        app.audit.record(req.ws.org.id, req.principal.actor, "create", "webhook", hook["id"], {"url": hook["url"]})
        return 201, hook
    r.add("POST", "/api/webhooks", create_webhook, admin=True)

    def delete_webhook(req):
        if not app.webhook_store.delete(req.ws.org.id, req.params["id"]):
            raise NotFound(req.params["id"])
        app.audit.record(req.ws.org.id, req.principal.actor, "delete", "webhook", req.params["id"])
        return 204, None
    r.add("DELETE", f"/api/webhooks/{_PID}", delete_webhook, admin=True)
    r.add("GET", f"/api/webhooks/{_PID}/deliveries",
          lambda req: _ok({"items": app.webhook_store.deliveries(req.ws.org.id, req.params["id"])}), admin=True)

    def test_webhook(req):
        if not app.webhook_store.get(req.ws.org.id, req.params["id"]):
            raise NotFound(req.params["id"])
        app.webhook_store.enqueue(req.params["id"], "ping", {"event": "ping", "organization_id": req.ws.org.id})
        return 202, {"queued": True}
    r.add("POST", f"/api/webhooks/{_PID}/test", test_webhook, admin=True)

    # --- banking ------------------------------------------------------------------------
    r.add("GET", "/api/bank/transactions",
          lambda req: _ok({"items": req.ws.bank.transactions(req.query.get("status") or None)}))
    r.add("GET", "/api/bank/insights", lambda req: _ok({
        "summary": req.ws.bank.summary(), "recurring_unknown": req.ws.bank.recurring(),
        "price_drift": req.ws.bank.price_drift()}))

    def bank_import(req):
        data, name, content = req.upload()
        return 201, req.ws.bank.import_statement(name, content, str(data.get("label") or ""))
    r.add("POST", "/api/bank/import", bank_import, max_body=MAX_UPLOAD_BODY)

    def bank_resolve(req):
        d = req.json()
        return _ok(req.ws.bank.resolve(req.params["id"], str(d.get("action") or ""), d.get("license_id")))
    r.add("POST", f"/api/bank/transactions/{_PID}", bank_resolve)

    def bank_connect(req):
        from .banking.connector import get_connector
        get_connector(req.query.get("provider"))
        return 200, {}
    r.add("GET", "/api/bank/connect", bank_connect, admin=True)

    # --- administration -------------------------------------------------------------------
    r.add("GET", "/api/audit", lambda req: _ok({"items": app.audit.recent(req.ws.org.id)}), admin=True)
    r.add("GET", "/api/system", lambda req: _ok({
        "schema_version": app.db.version(), "environment": app.settings.env,
        "tasks": scheduler.status if scheduler else {}, "rates_last_fetch": app.rates.store.last_fetch()}), admin=True)
    return r


def make_handler(app: App, static_dir: Path | None, scheduler=None) -> type[BaseHTTPRequestHandler]:
    router = build_router(app, scheduler)
    root = static_dir.resolve() if static_dir else None
    settings = app.settings

    class LicenseHandler(BaseHTTPRequestHandler):
        server_version = "LicensePulse"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def do_GET(self): self._dispatch("GET")
        def do_HEAD(self): self._dispatch("GET")
        def do_POST(self): self._dispatch("POST")
        def do_PUT(self): self._dispatch("PUT")
        def do_PATCH(self): self._dispatch("PATCH")
        def do_DELETE(self): self._dispatch("DELETE")

        def log_message(self, fmt: str, *args: Any) -> None:
            pass  # replaced by structured access log below

        def _client(self) -> str:
            if settings.trust_proxy and (fwd := self.headers.get("X-Forwarded-For")):
                return fwd.split(",")[0].strip()
            return self.client_address[0]

        def _dispatch(self, method: str) -> None:
            started = time.monotonic()
            self.request_id = self.headers.get("X-Request-Id", "")[:64] or uuid.uuid4().hex[:16]
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            self._actor, self._org = "-", "-"
            extra: dict[str, str] = {}
            try:
                if not path.startswith("/api/"):
                    status = self._static(path, method)
                else:
                    route, params = router.resolve(method, path)
                    body = self._read_body(route.max_body)
                    req = Request(method, path, dict(parse_qsl(url.query)), body, params)
                    self._authorize(route, req, method)
                    if body and "json" not in (self.headers.get("Content-Type") or ""):
                        raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type",
                                       "Tijelo zahtjeva mora biti application/json.")
                    status, payload = route.handler(req)
                    extra = req.extra_headers
                    self._send(status, payload, extra)
            except ApiError as e:
                status = e.status
                self._send(status, _error(e.code, e.message, e.fields))
            except AuthError as e:
                status = e.status
                headers = {"WWW-Authenticate": 'Basic realm="License Pulse", charset="UTF-8"'} if e.status == 401 else {}
                if e.retry_after:
                    headers["Retry-After"] = str(int(e.retry_after) + 1)
                self._send(status, _error("unauthorized" if e.status == 401 else "rate_limited", e.message), headers)
            except ValidationError as e:
                status = 422
                self._send(status, _error("validation_error", "Provjerite označena polja.", e.errors))
            except NotFound:
                status = 404
                self._send(status, _error("not_found", "Zapis ne postoji."))
            except ConnectorNotConfigured as e:
                status = 501
                self._send(status, _error("not_configured", str(e)))
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception:
                status = 500
                log.exception("unhandled_error", extra={"fields": {"request_id": self.request_id,
                                                                  "method": method, "path": path}})
                self._send(status, _error("internal", f"Greška poslužitelja (zahtjev {self.request_id})."))
            if settings.access_log and path != "/api/health":
                log.info("request", extra={"fields": {
                    "request_id": self.request_id, "method": method, "path": path, "status": int(status),
                    "ms": round((time.monotonic() - started) * 1000, 1), "client": self._client(),
                    "user": self._actor, "org": self._org}})

        def _authorize(self, route: Route, req: Request, method: str) -> None:
            if route.auth == "none":
                return
            auth = self.headers.get("Authorization")
            principal = app.authenticate(auth, self._client(), allow_token=route.auth == "token_or_user")
            if method not in ("GET", "HEAD") and principal.user is not None:
                if self.headers.get("X-Requested-With") != "LicensePulse":
                    raise ApiError(HTTPStatus.FORBIDDEN, "csrf", "Zahtjev nije poslan iz aplikacije.")
                origin = self.headers.get("Origin")
                if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                    raise ApiError(HTTPStatus.FORBIDDEN, "csrf", "Zahtjev s druge stranice nije dopušten.")
            if route.admin and not principal.is_admin:
                raise ApiError(HTTPStatus.FORBIDDEN, "forbidden", "Potrebna su administratorska prava.")
            req.principal = principal
            req.ws = app.workspace(principal.org, principal.actor)
            self._actor, self._org = principal.actor, principal.org.slug

        def _read_body(self, limit: int) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(HTTPStatus.BAD_REQUEST, "bad_length", "Neispravan Content-Length.") from None
            if length > limit:
                self.close_connection = True
                raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "too_large", "Zahtjev je prevelik.")
            return self.rfile.read(length) if length > 0 else b""

        def _headers(self, extra: dict[str, str]) -> None:
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            if settings.hsts:
                self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            self.send_header("X-Request-Id", self.request_id)
            for k, v in extra.items():
                self.send_header(k, v)

        def _send(self, status: int, payload: Any, extra: dict[str, str] | None = None) -> None:
            extra = dict(extra or {})
            if isinstance(payload, (bytes, bytearray)):
                data = bytes(payload)
            else:
                data = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
                if data:
                    extra.setdefault("Content-Type", "application/json; charset=utf-8")
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self._headers(extra)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _static(self, path: str, method: str) -> int:
            if method != "GET":
                raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Metoda nije dopuštena.")
            if root is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")
            if not PUBLIC_STATIC.match(path):
                # the page itself requires login, so the browser asks for credentials up front
                principal = app.authenticate(self.headers.get("Authorization"), self._client())
                self._actor, self._org = principal.actor, principal.org.slug
            rel = "index.html" if path == "/" else path.lstrip("/")
            target = (root / rel).resolve()
            if root not in target.parents or not target.is_file():  # blocks ../ traversal
                raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")
            data = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")   # revalidate: new deploys show at once
            self._headers({})
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            return 200

    return LicenseHandler


def _error(code: str, message: str, fields: dict | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if fields:
        err["fields"] = fields
    return {"error": err}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def create_server(app: App, host: str = "127.0.0.1", port: int = 8000, static_dir: Path | None = None,
                  scheduler=None) -> Server:
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    return Server((host, port), make_handler(app, static_dir, scheduler))
