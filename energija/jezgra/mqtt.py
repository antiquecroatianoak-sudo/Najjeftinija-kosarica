"""MQTT 3.1.1 – ugrađeni lokalni broker i klijent (QoS 0 i 1, zadržane poruke, zamjenski znakovi).

Jezgra sama pokreće broker, pa senzori (vlaga tla, ograda, releji) rade bez ikakvog
vanjskog poslužitelja. Broker može slušati preko TLS-a s certifikatom lokalnog CA-a.
Ovo nije potpuna implementacija standarda: nema QoS 2, trajnih sesija ni "will" poruka
osim osnovnog zapisa; za veće instalacije predviđen je Mosquitto (vidi ARHITEKTURA.md).
"""
from __future__ import annotations

import socket
import socketserver
import ssl
import struct
import threading
import time


def _duljina(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _str(s: str) -> bytes:
    b = s.encode()
    return struct.pack(">H", len(b)) + b


def _paket(tip: int, tijelo: bytes, zastavice: int = 0) -> bytes:
    return bytes([(tip << 4) | zastavice]) + _duljina(len(tijelo)) + tijelo


def _citaj_paket(s) -> tuple[int, int, bytes]:
    prvi = s.recv(1)
    if not prvi:
        raise ConnectionError("veza zatvorena")
    mn, n = 1, 0
    while True:
        b = s.recv(1)
        if not b:
            raise ConnectionError("veza zatvorena")
        n += (b[0] & 0x7F) * mn
        if not b[0] & 0x80:
            break
        mn *= 128
        if mn > 128 ** 3:
            raise ConnectionError("neispravna duljina")
    tijelo = b""
    while len(tijelo) < n:
        d = s.recv(n - len(tijelo))
        if not d:
            raise ConnectionError("veza zatvorena")
        tijelo += d
    return prvi[0] >> 4, prvi[0] & 0x0F, tijelo


def odgovara(filtar: str, tema: str) -> bool:
    f, t = filtar.split("/"), tema.split("/")
    for i, dio in enumerate(f):
        if dio == "#":
            return True
        if i >= len(t) or (dio != "+" and dio != t[i]):
            return False
    return len(f) == len(t)


class Broker:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, ssl_kontekst: ssl.SSLContext | None = None):
        self.zadrzane: dict[str, bytes] = {}
        self.pretplate: dict[object, list[str]] = {}
        self._lock = threading.Lock()
        nad = self

        class Rukovatelj(socketserver.BaseRequestHandler):
            def handle(self):
                s = self.request
                if ssl_kontekst:
                    s = ssl_kontekst.wrap_socket(s, server_side=True)
                veza = _Veza(s)
                try:
                    tip, _, _ = _citaj_paket(s)
                    if tip != 1:
                        return
                    veza.posalji(_paket(2, b"\x00\x00"))
                    with nad._lock:
                        nad.pretplate[veza] = []
                    while True:
                        tip, zast, tijelo = _citaj_paket(s)
                        if tip == 3:
                            nad._objava(veza, zast, tijelo)
                        elif tip == 8:
                            nad._pretplata(veza, tijelo)
                        elif tip == 12:
                            veza.posalji(_paket(13, b""))
                        elif tip == 14:
                            return
                except (ConnectionError, OSError, ssl.SSLError):
                    return
                finally:
                    with nad._lock:
                        nad.pretplate.pop(veza, None)

        class Srv(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._srv = Srv((host, port), Rukovatelj)
        self.port = self._srv.server_address[1]

    def _objava(self, veza, zast: int, tijelo: bytes) -> None:
        (n,) = struct.unpack(">H", tijelo[:2])
        tema = tijelo[2:2 + n].decode()
        pomak = 2 + n
        qos = (zast >> 1) & 3
        if qos:
            veza.posalji(_paket(4, tijelo[pomak:pomak + 2]))
            pomak += 2
        poruka = tijelo[pomak:]
        if zast & 1:
            if poruka:
                self.zadrzane[tema] = poruka
            else:
                self.zadrzane.pop(tema, None)
        self.distribuiraj(tema, poruka)

    def distribuiraj(self, tema: str, poruka: bytes) -> None:
        with self._lock:
            ciljevi = [v for v, f in self.pretplate.items() if any(odgovara(x, tema) for x in f)]
        p = _paket(3, _str(tema) + poruka)
        for v in ciljevi:
            v.posalji(p)

    def _pretplata(self, veza, tijelo: bytes) -> None:
        pid = tijelo[:2]
        i, filtri = 2, []
        while i < len(tijelo):
            (n,) = struct.unpack(">H", tijelo[i:i + 2])
            filtri.append(tijelo[i + 2:i + 2 + n].decode())
            i += 3 + n
        with self._lock:
            self.pretplate.setdefault(veza, []).extend(filtri)
        veza.posalji(_paket(9, pid + bytes([0] * len(filtri))))
        for tema, poruka in list(self.zadrzane.items()):
            if any(odgovara(f, tema) for f in filtri):
                veza.posalji(_paket(3, _str(tema) + poruka, 1))

    def pokreni(self) -> "Broker":
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def zaustavi(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()


class _Veza:
    def __init__(self, s):
        self.s = s
        self.lock = threading.Lock()

    def posalji(self, b: bytes) -> None:
        try:
            with self.lock:
                self.s.sendall(b)
        except OSError:
            pass


class Klijent:
    """Klijent s automatskim ponovnim spajanjem (eksponencijalno čekanje, najviše 60 s)."""

    def __init__(self, id_klijenta: str, host: str = "127.0.0.1", port: int = 1883,
                 ssl_kontekst: ssl.SSLContext | None = None, keepalive: int = 60):
        self.id, self.host, self.port, self.ssl, self.keepalive = id_klijenta, host, port, ssl_kontekst, keepalive
        self.pri_poruci = None
        self._filtri: list[str] = []
        self._s = None
        self._pid = 0
        self._radi = False
        self._lock = threading.Lock()
        self.spojen = threading.Event()

    def _spoji(self) -> None:
        s = socket.create_connection((self.host, self.port), timeout=10)
        if self.ssl:
            s = self.ssl.wrap_socket(s, server_hostname=self.host)
        s.settimeout(None)
        tijelo = _str("MQTT") + bytes([4, 0x02]) + struct.pack(">H", self.keepalive) + _str(self.id)
        s.sendall(_paket(1, tijelo))
        tip, _, odg = _citaj_paket(s)
        if tip != 2 or odg[1] != 0:
            raise ConnectionError("broker odbio vezu")
        self._s = s
        if self._filtri:
            self._posalji_pretplatu(self._filtri)
        self.spojen.set()

    def _posalji_pretplatu(self, filtri: list[str]) -> None:
        tijelo = struct.pack(">H", self._novi_pid()) + b"".join(_str(f) + b"\x00" for f in filtri)
        self._salji(_paket(8, tijelo, 0x02))

    def _novi_pid(self) -> int:
        self._pid = self._pid % 65535 + 1
        return self._pid

    def _salji(self, b: bytes) -> None:
        with self._lock:
            if self._s is None:
                raise ConnectionError("nije spojen")
            self._s.sendall(b)

    def pokreni(self) -> "Klijent":
        self._radi = True
        threading.Thread(target=self._petlja, daemon=True).start()
        threading.Thread(target=self._ping, daemon=True).start()
        return self

    def _petlja(self) -> None:
        cekaj = 1.0
        while self._radi:
            try:
                self._spoji()
                cekaj = 1.0
                while self._radi:
                    tip, zast, tijelo = _citaj_paket(self._s)
                    if tip == 3 and self.pri_poruci:
                        (n,) = struct.unpack(">H", tijelo[:2])
                        pomak = 2 + n + (2 if (zast >> 1) & 3 else 0)
                        try:
                            self.pri_poruci(tijelo[2:2 + n].decode(), tijelo[pomak:])
                        except Exception:
                            pass  # greška u obradi poruke ne prekida vezu
            except (OSError, ConnectionError, ssl.SSLError):
                self.spojen.clear()
                self._s = None
                if self._radi:
                    time.sleep(cekaj)
                    cekaj = min(cekaj * 2, 60.0)

    def _ping(self) -> None:
        while self._radi:
            time.sleep(self.keepalive / 2)
            try:
                self._salji(_paket(12, b""))
            except (OSError, ConnectionError):
                pass

    def pretplati(self, filtar: str) -> None:
        self._filtri.append(filtar)
        if self._s is not None:
            self._posalji_pretplatu([filtar])

    def objavi(self, tema: str, poruka: bytes | str, zadrzi: bool = False, qos: int = 0) -> bool:
        if isinstance(poruka, str):
            poruka = poruka.encode()
        tijelo = _str(tema) + (struct.pack(">H", self._novi_pid()) if qos else b"") + poruka
        try:
            self._salji(_paket(3, tijelo, (qos << 1) | (1 if zadrzi else 0)))
            return True
        except (OSError, ConnectionError):
            return False

    def zaustavi(self) -> None:
        self._radi = False
        try:
            self._salji(_paket(14, b""))
            self._s.close()
        except Exception:
            pass
