"""HTTP layer: a small JSON REST API plus static file serving.

Routes
  GET    /api/health
  GET    /api/meta                 enums for forms
  GET    /api/dashboard?days=30     totals, inactive and expiring licenses
  GET    /api/licenses?status=&category=&q=
  POST   /api/licenses
  GET    /api/licenses/{id}
  PUT    /api/licenses/{id}        full update
  PATCH  /api/licenses/{id}        partial update
  DELETE /api/licenses/{id}
"""
from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

from .models import BillingCycle, LicenseStatus, ValidationError
from .service import LicenseFilter, LicenseService, NotFound, parse_window

MAX_BODY = 64 * 1024

# Same-origin only: no inline scripts, no framing, no third-party requests.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
}
_ID = r"(?P<id>[0-9a-f]{32})"


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields


Handler = Callable[["Request"], tuple[HTTPStatus, Any]]


class Request:
    def __init__(self, method: str, path: str, query: dict[str, str], body: bytes, params: dict[str, str]):
        self.method, self.path, self.query, self.params = method, path, query, params
        self._body = body

    def json(self) -> Any:
        if not self._body:
            raise ApiError(HTTPStatus.BAD_REQUEST, "empty_body", "Nedostaje JSON tijelo zahtjeva.")
        try:
            return json.loads(self._body)
        except (ValueError, UnicodeDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_json", "Neispravan JSON.") from None


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append((method, re.compile(f"^{pattern}$"), handler))

    def resolve(self, method: str, path: str) -> tuple[Handler, dict[str, str]]:
        path_known = False
        for m, rx, handler in self._routes:
            match = rx.match(path)
            if match:
                path_known = True
                if m == method:
                    return handler, match.groupdict()
        if path_known:
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Metoda nije dopuštena.")
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")


def build_router(service: LicenseService) -> Router:
    r = Router()

    def one(req: Request):
        return HTTPStatus.OK, service.get(req.params["id"]).to_dict()

    r.add("GET", "/api/health", lambda req: (HTTPStatus.OK, {"status": "ok"}))
    r.add("GET", "/api/meta", lambda req: (HTTPStatus.OK, {
        "billing_cycles": [c.value for c in BillingCycle],
        "statuses": [s.value for s in LicenseStatus],
        "categories": service.categories(),
    }))
    r.add("GET", "/api/dashboard",
          lambda req: (HTTPStatus.OK, service.dashboard(parse_window(req.query.get("days")))))
    r.add("GET", "/api/licenses", lambda req: (HTTPStatus.OK, {
        "items": [l.to_dict() for l in service.list(LicenseFilter.from_params(req.query))]
    }))
    r.add("POST", "/api/licenses", lambda req: (HTTPStatus.CREATED, service.create(req.json()).to_dict()))
    r.add("GET", f"/api/licenses/{_ID}", one)
    r.add("PUT", f"/api/licenses/{_ID}",
          lambda req: (HTTPStatus.OK, service.replace(req.params["id"], req.json()).to_dict()))
    r.add("PATCH", f"/api/licenses/{_ID}",
          lambda req: (HTTPStatus.OK, service.patch(req.params["id"], req.json()).to_dict()))

    def delete(req: Request):
        service.delete(req.params["id"])
        return HTTPStatus.NO_CONTENT, None

    r.add("DELETE", f"/api/licenses/{_ID}", delete)
    return r


def make_handler(service: LicenseService, static_dir: Path | None) -> type[BaseHTTPRequestHandler]:
    router = build_router(service)
    root = static_dir.resolve() if static_dir else None

    class LicenseHandler(BaseHTTPRequestHandler):
        server_version = "LicenceApp/1.0"
        protocol_version = "HTTP/1.1"

        def do_GET(self): self._dispatch("GET")
        def do_POST(self): self._dispatch("POST")
        def do_PUT(self): self._dispatch("PUT")
        def do_PATCH(self): self._dispatch("PATCH")
        def do_DELETE(self): self._dispatch("DELETE")

        def log_message(self, fmt: str, *args: Any) -> None:  # quieter default log
            if getattr(self.server, "verbose", True):
                super().log_message(fmt, *args)

        def _dispatch(self, method: str) -> None:
            url = urlsplit(self.path)
            try:
                body = self._read_body()
                if not url.path.startswith("/api/"):
                    if method != "GET":
                        raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Metoda nije dopuštena.")
                    return self._static(url.path)
                handler, params = router.resolve(method, url.path.rstrip("/") or "/")
                if body and "json" not in (self.headers.get("Content-Type") or ""):
                    raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type",
                                   "Tijelo zahtjeva mora biti application/json.")
                status, payload = handler(Request(method, url.path, dict(parse_qsl(url.query)), body, params))
            except ApiError as e:
                status, payload = e.status, _error(e.code, e.message, e.fields)
            except ValidationError as e:
                status, payload = HTTPStatus.UNPROCESSABLE_ENTITY, _error(
                    "validation_error", "Provjerite označena polja.", e.errors)
            except NotFound:
                status, payload = HTTPStatus.NOT_FOUND, _error("not_found", "Licenca ne postoji.")
            except Exception:  # never leak internals to the client
                self.log_error("Unhandled error on %s %s", method, self.path)
                status, payload = HTTPStatus.INTERNAL_SERVER_ERROR, _error("internal", "Greška poslužitelja.")
            self._send_json(status, payload)

        def _read_body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(HTTPStatus.BAD_REQUEST, "bad_length", "Neispravan Content-Length.") from None
            if length > MAX_BODY:
                self.close_connection = True
                raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "too_large", "Zahtjev je prevelik.")
            return self.rfile.read(length) if length > 0 else b""

        def _send_json(self, status: HTTPStatus, payload: Any) -> None:
            data = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            if data:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)

        def _security_headers(self) -> None:
            for key, value in SECURITY_HEADERS.items():
                self.send_header(key, value)

        def _static(self, path: str) -> None:
            if root is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (root / rel).resolve()
            if root not in target.parents or not target.is_file():  # blocks ../ traversal
                raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "Nepostojeća adresa.")
            data = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")  # revalidate: new deploys show at once
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)

    return LicenseHandler


def _error(code: str, message: str, fields: dict | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if fields:
        err["fields"] = fields
    return {"error": err}


def create_server(service: LicenseService, host: str = "127.0.0.1", port: int = 8000,
                  static_dir: Path | None = None, verbose: bool = True) -> ThreadingHTTPServer:
    mimetypes.add_type("text/javascript", ".js")
    server = ThreadingHTTPServer((host, port), make_handler(service, static_dir))
    server.verbose = verbose  # type: ignore[attr-defined]
    return server
