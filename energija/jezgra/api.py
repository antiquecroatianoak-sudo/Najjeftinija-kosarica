"""Lokalni HTTPS API i sučelje (radi bez interneta, u lokalnoj mreži ili kroz tunel).

Pristup: uparivanje kodom od 6 znamenki koji jezgra prikaže pri prvom pokretanju (konzola,
zaslon uređaja ili naljepnica/QR) i vrijedi 15 minuta. Uređaj koji upiše kod dobije token
(u bazi se čuva samo njegov SHA-256). Bez tokena dostupna je samo provjera zdravlja.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import ssl
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import izvjestaji

SUCELJE = Path(__file__).resolve().parent.parent / "sucelje"
ZABRANJENO_RUCNO = {"pastir", "pumpa"}  # pastir: zaštita stoke; pumpa: samo kroz navodnjavanje (ventili)


class Pristup:
    def __init__(self, mapa: Path, prozor_s: float = 900):
        self.p = Path(mapa) / "pristup.json"
        self.tokeni: dict[str, dict] = {}
        if self.p.exists():
            try:
                self.tokeni = json.loads(self.p.read_text())
            except ValueError:
                pass
        self.kod = f"{secrets.randbelow(10 ** 6):06d}"
        self.kod_do = time.time() + prozor_s
        self.pokusaji = 0

    def upari(self, kod: str, ime: str) -> str | None:
        if time.time() > self.kod_do or self.pokusaji >= 10:
            return None
        self.pokusaji += 1
        if not hmac.compare_digest(str(kod), self.kod):
            return None
        token = secrets.token_hex(32)
        self.tokeni[hashlib.sha256(token.encode()).hexdigest()] = {"ime": ime[:40], "od": time.time()}
        tmp = self.p.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.tokeni, f)
        os.replace(tmp, self.p)
        self.kod_do = 0  # kod je jednokratan
        return token

    def provjeri(self, token: str | None) -> bool:
        return bool(token) and hashlib.sha256(token.encode()).hexdigest() in self.tokeni

    def novi_prozor(self, prozor_s: float = 900) -> str:
        """Npr. nakon pritiska tipke na kućištu: novi kod za uparivanje dodatnog mobitela."""
        self.kod, self.kod_do, self.pokusaji = f"{secrets.randbelow(10 ** 6):06d}", time.time() + prozor_s, 0
        return self.kod


def obradi(jezgra, metoda: str, put: str, upit: dict, tijelo: dict | None) -> tuple[int, str, bytes]:
    """Zajednička obrada za HTTP i tunel. Vraća (status, content-type, tijelo)."""
    j = jezgra
    if metoda == "GET" and put == "/api/stanje":
        return 200, "application/json", json.dumps(j.stanje(), default=str).encode()
    if metoda == "GET" and put == "/api/izvjestaj":
        dana = float(upit.get("dana", ["7"])[0])
        do = j.sat()
        izv = j.izvjestaj(do - dana * 86400, do, izvezi=False)
        potpis = izvjestaji.potpisi(izv, j.trezor)
        oblik = upit.get("format", ["html"])[0]
        if oblik == "json":
            return 200, "application/json", json.dumps({"izvjestaj": izv, "potpis": potpis}).encode()
        if oblik == "csv":
            return 200, "text/csv; charset=utf-8", izvjestaji.u_csv(izv).encode()
        return 200, "text/html; charset=utf-8", izvjestaji.u_html(izv, potpis).encode()
    if metoda == "POST" and put == "/api/naredba":
        t = (tijelo or {}).get("trosilo", "")
        if t in ZABRANJENO_RUCNO or t not in j.releji:
            return 400, "application/json", b'{"greska":"nepoznato ili zasticeno trosilo"}'
        minuta = max(1, min(240, int((tijelo or {}).get("minuta", 30))))
        j.rucno[t] = (bool(tijelo.get("ukljuci")), j.sat() + minuta * 60)
        j._dogadjaj("naredba", {"poruka": f"Ručno: {t} {'uključeno' if tijelo.get('ukljuci') else 'isključeno'} "
                                          f"{minuta} min", "trosilo": t})
        return 200, "application/json", b'{"ok":true}'
    if metoda == "POST" and put == "/api/kopija":
        r = j.napravi_kopiju()
        return 200, "application/json", json.dumps(r).encode()
    return 404, "application/json", b'{"greska":"nema"}'


def pokreni_api(jezgra, port: int, tls: bool = True, host: str = "0.0.0.0"):
    pristup = Pristup(jezgra.mapa)
    jezgra.kod_uparivanja = pristup.kod
    jezgra.pristup = pristup
    if not hasattr(jezgra, "rucno"):
        jezgra.rucno = {}

    class H(BaseHTTPRequestHandler):
        server_version = "Energija"

        def log_message(self, *a):  # bez zapisivanja svakog zahtjeva na SD karticu
            pass

        def _salji(self, status: int, vrsta: str, tijelo: bytes, dodatno: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", vrsta)
            self.send_header("Content-Length", str(len(tijelo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                        "img-src 'self' data:; frame-ancestors 'none'")
            for k, v in (dodatno or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(tijelo)

        def _token(self) -> str | None:
            a = self.headers.get("Authorization", "")
            if a.startswith("Bearer "):
                return a[7:]
            for dio in self.headers.get("Cookie", "").split(";"):
                k, _, v = dio.strip().partition("=")
                if k == "energija":
                    return v
            return None

        def _tijelo(self) -> dict:
            n = min(int(self.headers.get("Content-Length", 0) or 0), 65536)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n))
            except ValueError:
                return {}

        def _obradi(self, metoda: str):
            u = urllib.parse.urlparse(self.path)
            put, upit = u.path, urllib.parse.parse_qs(u.query)
            if put == "/api/zdravlje":
                return self._salji(200, "application/json", b'{"ok":true}')
            if put == "/api/upari" and metoda == "POST":
                t = self._tijelo()
                token = pristup.upari(t.get("kod", ""), t.get("ime", "uredaj"))
                if not token:
                    return self._salji(403, "application/json", b'{"greska":"kod nije ispravan ili je istekao"}')
                kolac = f"energija={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000" + \
                        ("; Secure" if tls else "")
                return self._salji(200, "application/json", json.dumps({"token": token}).encode(),
                                   {"Set-Cookie": kolac})
            if put.startswith("/api/"):
                if not pristup.provjeri(self._token()):
                    return self._salji(401, "application/json", b'{"greska":"potrebno uparivanje"}')
                try:
                    s, v, b = obradi(jezgra, metoda, put, upit, self._tijelo() if metoda == "POST" else None)
                except Exception as e:
                    s, v, b = 500, "application/json", json.dumps({"greska": f"{type(e).__name__}"}).encode()
                return self._salji(s, v, b)
            if metoda != "GET":
                return self._salji(405, "text/plain", b"")
            ime = "index.html" if put in ("/", "") else put.lstrip("/")
            p = (SUCELJE / ime).resolve()
            if SUCELJE.resolve() not in p.parents or not p.is_file():
                return self._salji(404, "text/plain", b"nema")
            vrsta = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if vrsta.startswith("text/") or vrsta.endswith("javascript"):
                vrsta += "; charset=utf-8"
            return self._salji(200, vrsta, p.read_bytes())

        def do_GET(self):
            self._obradi("GET")

        def do_POST(self):
            self._obradi("POST")

    srv = ThreadingHTTPServer((host, port), H)
    srv.daemon_threads = True
    if tls:
        from .certifikati import LokalniCA
        ctx = LokalniCA(jezgra.mapa, jezgra.trezor).kontekst_posluzitelja()
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)  # rukovanje u niti zahtjeva
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    adresa = f"{'https' if tls else 'http'}://localhost:{srv.server_address[1]}/"
    return srv, adresa


def obrada_tunela(jezgra):
    """Za TunelJezgre: {"metoda","put","upit","tijelo"} -> {"status","vrsta","tijelo"}."""
    def f(z: dict) -> dict:
        s, v, b = obradi(jezgra, z.get("metoda", "GET"), z.get("put", ""), z.get("upit", {}), z.get("tijelo"))
        return {"status": s, "vrsta": v, "tijelo": b.decode("utf-8", "replace")}
    return f
