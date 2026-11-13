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

from . import api_v1, izvjestaji

SUCELJE = Path(__file__).resolve().parent.parent / "sucelje"
ZABRANJENO_RUCNO = {"pastir", "pumpa"}  # pastir: zaštita stoke; pumpa: samo kroz navodnjavanje (ventili)


class Pristup:
    """Tokeni s ulogama. Kod s kućišta/konzole daje administratora; administrator izdaje pozivnice
    (jednokratni kodovi) za stanare i integracije. U bazi se čuva samo SHA-256 tokena."""

    ULOGE = ("stanar", "integracija", "administrator")

    def __init__(self, mapa: Path, prozor_s: float = 900):
        self.p = Path(mapa) / "pristup.json"
        self.tokeni: dict[str, dict] = {}
        if self.p.exists():
            try:
                self.tokeni = json.loads(self.p.read_text())
            except ValueError:
                pass
        for v in self.tokeni.values():  # tokeni iz ranijih verzija bili su administratorski
            v.setdefault("uloga", "administrator")
        # ENERGIJA_KOD: samo za automatsku izoliranu provjeru (Compose); i dalje jednokratan i vrijedi 15 min
        zadani = os.environ.get("ENERGIJA_KOD", "")
        self.kod = zadani if len(zadani) == 6 and zadani.isdigit() else f"{secrets.randbelow(10 ** 6):06d}"
        self.kod_do = time.time() + prozor_s
        self.pokusaji = 0
        self.pozivnice: dict[str, dict] = {}  # kod -> {uloga, do}

    def _spremi(self) -> None:
        tmp = self.p.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.tokeni, f)
        os.replace(tmp, self.p)

    def upari(self, kod: str, ime: str) -> tuple[str, str] | None:
        """Vraća (token, uloga) ili None. Kodovi su jednokratni; najviše 10 pogrešnih pokušaja po prozoru."""
        if self.pokusaji >= 10:
            return None
        self.pokusaji += 1
        kod = str(kod)
        uloga = None
        if time.time() <= self.kod_do and hmac.compare_digest(kod, self.kod):
            uloga, self.kod_do = "administrator", 0
        else:
            for k, v in list(self.pozivnice.items()):
                if v["do"] < time.time():
                    self.pozivnice.pop(k)
                elif hmac.compare_digest(kod, k):
                    uloga = self.pozivnice.pop(k)["uloga"]
        if not uloga:
            return None
        self.pokusaji = 0
        token = secrets.token_hex(32)
        self.tokeni[hashlib.sha256(token.encode()).hexdigest()] = {"ime": ime[:40], "od": time.time(), "uloga": uloga}
        self._spremi()
        return token, uloga

    def pozivnica(self, uloga: str, prozor_s: float = 3600) -> dict:
        if uloga not in self.ULOGE:
            raise ValueError(f"uloga: {self.ULOGE}")
        kod = f"{secrets.randbelow(10 ** 8):08d}"
        self.pozivnice[kod] = {"uloga": uloga, "do": time.time() + prozor_s}
        self.pokusaji = 0
        return {"kod": kod, "uloga": uloga, "do": self.pozivnice[kod]["do"]}

    def uloga(self, token: str | None) -> str | None:
        if not token:
            return None
        v = self.tokeni.get(hashlib.sha256(token.encode()).hexdigest())
        return v["uloga"] if v else None

    def provjeri(self, token: str | None) -> bool:
        return self.uloga(token) is not None

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
    if put == "/api/postavke":
        if metoda == "POST":
            try:
                j.postavi_napredno(tijelo or {})
            except (ValueError, TypeError) as e:
                return 400, "application/json", json.dumps({"greska": str(e)}).encode()
        return 200, "application/json", json.dumps({"napredno": j.napredno, "ai_aktivan": j.ai_aktivan,
                                                    "provjera": j.ai_provjera}).encode()
    if metoda == "POST" and put == "/api/ai/provjera":
        return 200, "application/json", json.dumps(j.primijeni_ai_profil("ručna provjera")).encode()
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

    brava = threading.Lock()
    aktivni_tokovi = [0]

    class H(BaseHTTPRequestHandler):
        server_version = "Energija"

        def log_message(self, *a):  # bez zapisivanja svakog zahtjeva na SD karticu
            pass

        def _cors(self) -> dict:
            izvor = self.headers.get("Origin")
            dopusteni = jezgra.cfg["api"].get("cors_izvori", [])
            if izvor and (izvor in dopusteni or "*" in dopusteni):
                return {"Access-Control-Allow-Origin": izvor, "Vary": "Origin",
                        "Access-Control-Allow-Headers": "Authorization, Content-Type",
                        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                        "Access-Control-Allow-Credentials": "true"}
            return {}

        def _salji(self, status: int, vrsta: str, tijelo: bytes, dodatno: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", vrsta)
            self.send_header("Content-Length", str(len(tijelo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                        "img-src 'self' data:; frame-ancestors 'none'")
            for k, v in {**self._cors(), **(dodatno or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(tijelo)

        def _json(self, status: int, podaci, dodatno: dict | None = None):
            self._salji(status, "application/json; charset=utf-8",
                        json.dumps(podaci, default=str, ensure_ascii=False).encode(), dodatno)

        def _token(self, upit: dict | None = None) -> str | None:
            a = self.headers.get("Authorization", "")
            if a.startswith("Bearer "):
                return a[7:]
            if upit and "token" in upit:  # samo za /api/v1/uzivo (EventSource ne šalje zaglavlja)
                return upit["token"][0]
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
            if metoda == "OPTIONS":
                return self._salji(204, "text/plain", b"")
            if put in ("/api/zdravlje", "/api/v1/zdravlje"):
                return self._salji(200, "application/json", b'{"ok":true}')
            if put == "/api/v1/openapi.json":
                return self._json(200, api_v1.openapi())
            if put in ("/api/upari", "/api/v1/upari") and metoda == "POST":
                t = self._tijelo()
                r = pristup.upari(t.get("kod", ""), t.get("ime", "uredaj"))
                if not r:
                    return self._json(403, {"greska": "kod nije ispravan ili je istekao"})
                token, uloga = r
                kolac = f"energija={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000" + \
                        ("; Secure" if tls else "")
                jezgra._dogadjaj("pristup", {"poruka": f"Upareno: {t.get('ime', 'uredaj')[:40]} ({uloga})"})
                return self._json(200, {"token": token, "uloga": uloga}, {"Set-Cookie": kolac})
            if put.startswith("/api/v1/"):
                uloga = pristup.uloga(self._token(upit if put == "/api/v1/uzivo" else None))
                if not uloga:
                    return self._json(401, {"greska": "potrebno uparivanje", "dokumentacija": "/api/v1/openapi.json"})
                if put == "/api/v1/uzivo":
                    return self._uzivo()
                if put == "/api/v1/pristup/pozivnice" and metoda == "POST":
                    if uloga != "administrator":
                        return self._json(403, {"greska": "samo administrator"})
                    try:
                        return self._json(200, pristup.pozivnica(self._tijelo().get("uloga", "stanar")))
                    except ValueError as e:
                        return self._json(400, {"greska": str(e)})
                try:
                    s, podaci = api_v1.obradi(jezgra, uloga, metoda, put, upit,
                                              self._tijelo() if metoda in ("POST", "DELETE") else None)
                except Exception as e:  # nikad ne otkrivaj trag; jezgra radi dalje
                    s, podaci = 500, {"greska": type(e).__name__}
                return self._json(s, podaci)
            if put.startswith("/api/"):  # stari API (sučelje v0) – samo administrator; novi klijenti: /api/v1
                if pristup.uloga(self._token()) != "administrator":
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

        def _uzivo(self):
            """SSE: događaj 'stanje' svake 2 s; najviše 8 istodobnih tokova (štedi uređaj)."""
            with brava:
                if aktivni_tokovi[0] >= 8:
                    return self._json(503, {"greska": "previše istodobnih tokova uživo"})
                aktivni_tokovi[0] += 1
            try:
                self.send_response(200)
                for k, v in {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store",
                             "X-Accel-Buffering": "no", **self._cors()}.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(b"retry: 3000\n\n")
                kraj = time.time() + 3600  # klijent se sam ponovno spaja
                while time.time() < kraj:
                    self.wfile.write(api_v1.uzivo_poruka(jezgra).encode())
                    self.wfile.flush()
                    time.sleep(2.0)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with brava:
                    aktivni_tokovi[0] -= 1

        def do_GET(self):
            self._obradi("GET")

        def do_POST(self):
            self._obradi("POST")

        def do_DELETE(self):
            self._obradi("DELETE")

        def do_OPTIONS(self):
            self._obradi("OPTIONS")

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
        put = z.get("put", "")
        if put.startswith("/api/v1/"):  # tunel: identitet je već provjeren ključem -> administrator
            s, podaci = api_v1.obradi(jezgra, "administrator", z.get("metoda", "GET"), put, z.get("upit", {}),
                                      z.get("tijelo"))
            return {"status": s, "vrsta": "application/json", "tijelo": json.dumps(podaci, default=str)}
        s, v, b = obradi(jezgra, z.get("metoda", "GET"), put, z.get("upit", {}), z.get("tijelo"))
        return {"status": s, "vrsta": v, "tijelo": b.decode("utf-8", "replace")}
    return f
