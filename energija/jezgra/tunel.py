"""Sigurni tunel za daljinsko održavanje i P2P pristup bez podešavanja mreže.

- Jezgra se sama spaja VAN (TLS) prema releju, pa nije potrebno otvarati portove na
  usmjerniku ni imati javnu IP adresu (radi i iza mobilnog interneta / CGNAT-a).
- Klijent (vlasnik ili tehničar) se spaja na relej s ID-om jezgre; relej samo spaja dva
  toka bajtova.
- Unutar toga obje strane rade Sesija rukovanje (X25519 + Ed25519): kraj-do-kraja
  šifrirano i dvosmjerno; relej ne vidi sadržaj i ne može se lažno predstaviti.
- Jezgra prihvaća samo identitete s popisa ovlaštenih (upareni uređaji vlasnika; ključ
  tehničara samo dok vlasnik dopusti održavanje).
- U istoj lokalnoj mreži klijent se spaja izravno na jezgru (P2P, otkrivanje multicastom),
  istim protokolom i bez releja.
- Kroz tunel se ne otvara ljuska: dopušteni su samo API zahtjevi jezgre.

Ograničenje prototipa: izravno P2P povezivanje preko interneta (UDP hole punching) nije
implementirano; izvan LAN-a promet ide preko releja (i dalje kraj-do-kraja šifriran).
"""
from __future__ import annotations

import json
import socket
import socketserver
import ssl
import struct
import threading
import time

from .sifra import GreskaSifre, Sesija


def posalji_okvir(s, b: bytes) -> None:
    s.sendall(struct.pack(">I", len(b)) + b)


def primi_okvir(s, max_duljina: int = 8 << 20) -> bytes:
    def tocno(n: int) -> bytes:
        b = b""
        while len(b) < n:
            d = s.recv(n - len(b))
            if not d:
                raise ConnectionError("veza zatvorena")
            b += d
        return b
    (n,) = struct.unpack(">I", tocno(4))
    if n > max_duljina:
        raise ConnectionError("prevelik okvir")
    return tocno(n)


# ------------------------------------------------------------------ relej (oblak / VPS)
class Relej:
    """Spaja jezgru i klijenta po ID-u. Ne zna ključeve i ne može čitati promet."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, ssl_kontekst: ssl.SSLContext | None = None):
        self.cekaju: dict[str, socket.socket] = {}
        self._lock = threading.Lock()
        nad = self

        class Rukovatelj(socketserver.BaseRequestHandler):
            def handle(self):
                s = self.request
                if ssl_kontekst:
                    s = ssl_kontekst.wrap_socket(s, server_side=True)
                try:
                    z = json.loads(primi_okvir(s, 4096))
                    if z.get("uloga") == "jezgra":
                        gotovo = threading.Event()
                        with nad._lock:
                            stari = nad.cekaju.pop(z["id"], None)
                            nad.cekaju[z["id"]] = (s, gotovo)
                        if stari:
                            stari[1].set()  # zamijenjena prijava iste jezgre
                        gotovo.wait(6 * 3600)  # drži vezu dok traje par (ili istek)
                    elif z.get("uloga") == "klijent":
                        with nad._lock:
                            par = nad.cekaju.pop(z["id"], None)
                        if par is None:
                            posalji_okvir(s, b'{"ok":false,"razlog":"jezgra nije spojena"}')
                            return
                        j, gotovo = par
                        try:
                            posalji_okvir(j, b'{"ok":true}')
                            posalji_okvir(s, b'{"ok":true}')
                            t = threading.Thread(target=_cijev, args=(j, s), daemon=True)
                            t.start()
                            _cijev(s, j)
                            t.join()
                        finally:
                            gotovo.set()
                except (ConnectionError, OSError, ValueError, ssl.SSLError):
                    return

        class Srv(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._srv = Srv((host, port), Rukovatelj)
        self.port = self._srv.server_address[1]

    def pokreni(self) -> "Relej":
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def zaustavi(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()


def _cijev(a, b) -> None:
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    finally:
        for x in (a, b):
            try:
                x.close()
            except OSError:
                pass


# ------------------------------------------------------------------ strana jezgre
class TunelJezgre:
    def __init__(self, trezor, ovlasteni, obrada):
        """ovlasteni: callable -> set javnih ključeva (bytes); obrada(zahtjev dict) -> dict."""
        self.trezor = trezor
        self.ovlasteni = ovlasteni
        self.obrada = obrada
        self._radi = False
        self.zadnja_greska: str | None = None
        self.sesija_aktivna = 0

    def posluzi(self, s) -> None:
        """Rukovanje + petlja zahtjeva na već uspostavljenoj vezi (relej ili izravno)."""
        ses = Sesija(self.trezor, "jezgra")
        try:
            posalji_okvir(s, ses.pozdrav())
            ses.dovrsi(primi_okvir(s, 256), self.ovlasteni())
        except (GreskaSifre, ConnectionError, OSError) as e:
            self.zadnja_greska = str(e)
            s.close()
            return
        self.sesija_aktivna += 1
        try:
            while True:
                zahtjev = json.loads(ses.desifriraj(primi_okvir(s)))
                try:
                    odg = self.obrada(zahtjev)
                except Exception as e:  # greška obrade ne ruši tunel
                    odg = {"greska": f"{type(e).__name__}: {e}"}
                posalji_okvir(s, ses.sifriraj(json.dumps(odg).encode()))
        except (GreskaSifre, ConnectionError, OSError, ValueError):
            pass
        finally:
            self.sesija_aktivna -= 1
            s.close()

    def preko_releja(self, host: str, port: int, ssl_kontekst: ssl.SSLContext | None) -> "TunelJezgre":
        """Drži jednu prijavljenu vezu prema releju; nakon uparivanja otvara sljedeću."""
        self._radi = True

        def petlja():
            cekaj = 2.0
            while self._radi:
                try:
                    s = socket.create_connection((host, port), timeout=15)
                    if ssl_kontekst:
                        s = ssl_kontekst.wrap_socket(s, server_hostname=host)
                    s.settimeout(None)
                    posalji_okvir(s, json.dumps({"uloga": "jezgra", "id": self.trezor.id_uredaja()}).encode())
                    odg = json.loads(primi_okvir(s, 4096))
                    if odg.get("ok"):
                        cekaj = 2.0
                        threading.Thread(target=self.posluzi, args=(s,), daemon=True).start()
                        continue
                except (OSError, ConnectionError, ValueError, ssl.SSLError) as e:
                    self.zadnja_greska = str(e)
                time.sleep(cekaj)
                cekaj = min(300.0, cekaj * 2)  # štedi bateriju i podatke dok je relej nedostupan

        threading.Thread(target=petlja, daemon=True).start()
        return self

    def izravno(self, host: str = "0.0.0.0", port: int = 0) -> int:
        """LAN P2P: sluša izravne veze klijenata. Vraća port."""
        nad = self

        class Rukovatelj(socketserver.BaseRequestHandler):
            def handle(self):
                nad.posluzi(self.request)

        class Srv(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._srv = Srv((host, port), Rukovatelj)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self._srv.server_address[1]

    def zaustavi(self) -> None:
        self._radi = False
        if hasattr(self, "_srv"):
            self._srv.shutdown()
            self._srv.server_close()


# ------------------------------------------------------------------ strana klijenta
class TunelKlijent:
    def __init__(self, kljuc_identiteta, javni_kljuc_jezgre: bytes):
        self.kljuc = kljuc_identiteta
        self.jezgra = javni_kljuc_jezgre
        self.s = None
        self.ses: Sesija | None = None

    def _rukovanje(self, s) -> None:
        self.ses = Sesija(self.kljuc, "klijent")
        posalji_okvir(s, self.ses.pozdrav())
        self.ses.dovrsi(primi_okvir(s, 256), {self.jezgra})
        self.s = s

    def spoji_izravno(self, host: str, port: int) -> "TunelKlijent":
        self._rukovanje(socket.create_connection((host, port), timeout=10))
        return self

    def spoji_relej(self, host: str, port: int, id_jezgre: str, ssl_kontekst: ssl.SSLContext | None) -> "TunelKlijent":
        s = socket.create_connection((host, port), timeout=10)
        if ssl_kontekst:
            s = ssl_kontekst.wrap_socket(s, server_hostname=host)
        posalji_okvir(s, json.dumps({"uloga": "klijent", "id": id_jezgre}).encode())
        odg = json.loads(primi_okvir(s, 4096))
        if not odg.get("ok"):
            raise ConnectionError(odg.get("razlog", "relej odbio"))
        self._rukovanje(s)
        return self

    def zahtjev(self, z: dict) -> dict:
        posalji_okvir(self.s, self.ses.sifriraj(json.dumps(z).encode()))
        return json.loads(self.ses.desifriraj(primi_okvir(self.s)))

    def zatvori(self) -> None:
        if self.s:
            self.s.close()
