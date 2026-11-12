"""Modbus TCP (klijent i poslužitelj) bez vanjskih paketa.

Podržane funkcije: 3 (holding), 4 (input), 6 (upis jednog registra), 16 (upis više registara).
Klijent ima vremensko ograničenje, ponovno spajanje i ponovne pokušaje; greške uređaja
(exception odgovori) vraćaju se kao ModbusGreska, a ne ruše jezgru.
Za RS-485 (Modbus RTU) isti okvir PDU-a vrijedi preko serijskog pretvarača – vidi ARHITEKTURA.md.
"""
from __future__ import annotations

import socket
import socketserver
import struct
import threading


class ModbusGreska(Exception):
    pass


def u_float(regs: list[int], i: int = 0) -> float:
    return struct.unpack(">f", struct.pack(">HH", regs[i], regs[i + 1]))[0]


def iz_floata(v: float) -> list[int]:
    a, b = struct.unpack(">HH", struct.pack(">f", float(v)))
    return [a, b]


def u_int16(r: int) -> int:
    return r - 0x10000 if r & 0x8000 else r


class ModbusKlijent:
    def __init__(self, host: str, port: int = 502, timeout: float = 1.5, pokusaja: int = 2):
        self.host, self.port, self.timeout, self.pokusaja = host, port, timeout, pokusaja
        self._s: socket.socket | None = None
        self._tid = 0
        self._lock = threading.Lock()

    def _spoji(self) -> socket.socket:
        if self._s is None:
            self._s = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._s.settimeout(self.timeout)
        return self._s

    def zatvori(self) -> None:
        if self._s:
            try:
                self._s.close()
            finally:
                self._s = None

    def _primi(self, s: socket.socket, n: int) -> bytes:
        b = b""
        while len(b) < n:
            d = s.recv(n - len(b))
            if not d:
                raise ConnectionError("uređaj je zatvorio vezu")
            b += d
        return b

    def _zahtjev(self, jedinica: int, pdu: bytes) -> bytes:
        zadnja: Exception | None = None
        with self._lock:
            for _ in range(self.pokusaja):
                try:
                    s = self._spoji()
                    self._tid = (self._tid + 1) & 0xFFFF
                    s.sendall(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, jedinica) + pdu)
                    tid, _, duljina, _ = struct.unpack(">HHHB", self._primi(s, 7))
                    odg = self._primi(s, duljina - 1)
                    if tid != self._tid:
                        raise ConnectionError("pomiješani odgovori")
                    if odg[0] & 0x80:
                        raise ModbusGreska(f"uređaj vratio grešku {odg[1]} za funkciju {odg[0] & 0x7F}")
                    return odg
                except ModbusGreska:
                    raise
                except (OSError, ConnectionError, struct.error) as e:
                    zadnja = e
                    self.zatvori()
        raise ConnectionError(f"Modbus {self.host}:{self.port} nedostupan: {zadnja}")

    def _citaj(self, fn: int, jedinica: int, adresa: int, broj: int) -> list[int]:
        odg = self._zahtjev(jedinica, struct.pack(">BHH", fn, adresa, broj))
        n = odg[1] // 2
        return list(struct.unpack(f">{n}H", odg[2:2 + 2 * n]))

    def citaj_holding(self, jedinica: int, adresa: int, broj: int) -> list[int]:
        return self._citaj(3, jedinica, adresa, broj)

    def citaj_input(self, jedinica: int, adresa: int, broj: int) -> list[int]:
        return self._citaj(4, jedinica, adresa, broj)

    def upisi(self, jedinica: int, adresa: int, vrijednost: int) -> None:
        self._zahtjev(jedinica, struct.pack(">BHH", 6, adresa, vrijednost & 0xFFFF))

    def upisi_vise(self, jedinica: int, adresa: int, vrijednosti: list[int]) -> None:
        n = len(vrijednosti)
        self._zahtjev(jedinica, struct.pack(f">BHHB{n}H", 16, adresa, n, 2 * n, *vrijednosti))


class Registri:
    """Registri jedne jedinice (za simulaciju uređaja ili kad jezgra sama izlaže podatke)."""

    def __init__(self):
        self.holding: dict[int, int] = {}
        self.input: dict[int, int] = {}
        self.lock = threading.Lock()

    def postavi(self, tablica: str, adresa: int, vrijednosti: list[int]) -> None:
        with self.lock:
            t = getattr(self, tablica)
            for i, v in enumerate(vrijednosti):
                t[adresa + i] = v & 0xFFFF


class ModbusPosluzitelj:
    def __init__(self, jedinice: dict[int, Registri], host: str = "127.0.0.1", port: int = 0,
                 pri_upisu=None):
        self.jedinice = jedinice
        self.pri_upisu = pri_upisu
        nad = self

        class Rukovatelj(socketserver.BaseRequestHandler):
            def handle(self):
                s = self.request
                while True:
                    z = b""
                    while len(z) < 7:
                        d = s.recv(7 - len(z))
                        if not d:
                            return
                        z += d
                    tid, proto, duljina, jed = struct.unpack(">HHHB", z)
                    pdu = b""
                    while len(pdu) < duljina - 1:
                        d = s.recv(duljina - 1 - len(pdu))
                        if not d:
                            return
                        pdu += d
                    odg = nad._obradi(jed, pdu)
                    s.sendall(struct.pack(">HHHB", tid, proto, len(odg) + 1, jed) + odg)

        class Srv(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._srv = Srv((host, port), Rukovatelj)
        self.port = self._srv.server_address[1]
        self._nit = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def _obradi(self, jed: int, pdu: bytes) -> bytes:
        fn = pdu[0]
        r = self.jedinice.get(jed)
        if r is None:
            return bytes([fn | 0x80, 0x0B])  # gateway target failed to respond
        try:
            if fn in (3, 4):
                adr, n = struct.unpack(">HH", pdu[1:5])
                t = r.holding if fn == 3 else r.input
                with r.lock:
                    if any((adr + i) not in t for i in range(n)):
                        return bytes([fn | 0x80, 0x02])
                    v = [t[adr + i] for i in range(n)]
                return struct.pack(f">BB{n}H", fn, 2 * n, *v)
            if fn == 6:
                adr, v = struct.unpack(">HH", pdu[1:5])
                r.postavi("holding", adr, [v])
                if self.pri_upisu:
                    self.pri_upisu(jed, adr, [v])
                return pdu[:5]
            if fn == 16:
                adr, n, _ = struct.unpack(">HHB", pdu[1:6])
                v = list(struct.unpack(f">{n}H", pdu[6:6 + 2 * n]))
                r.postavi("holding", adr, v)
                if self.pri_upisu:
                    self.pri_upisu(jed, adr, v)
                return struct.pack(">BHH", 16, adr, n)
        except struct.error:
            return bytes([fn | 0x80, 0x03])
        return bytes([fn | 0x80, 0x01])

    def pokreni(self) -> "ModbusPosluzitelj":
        self._nit.start()
        return self

    def zaustavi(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()
