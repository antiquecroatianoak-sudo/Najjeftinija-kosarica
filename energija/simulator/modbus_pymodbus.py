"""Simulirana farma kao stvarni Modbus TCP uređaji (pymodbus) + MQTT senzori.

Jedinica 1: hibridni izmjenjivač s baterijom po SunSpec mapi (modeli 1, 103, 124).
Jedinica 2: Eastron SDM630 brojilo na priključku mreže (input registri, IEEE754 float).
MQTT (na broker jezgre): vlaga tla, pastir, pumpa, bojler + naredbe relejima, s najavom
`energija/otkrij/sim-farma`, kao što bi to radio stvarni pristupnik senzora.

Fizika dolazi iz `jezgra.simulacija.Lokacija` (ista kao u brzim simulacijama), ubrzana
faktorom `--brzina`. Upisi jezgre u Modbus registre (upravljanje baterijom) i MQTT naredbe
djeluju na model, a `/stanje` (HTTP) izlaže stanje simulatora za automatsku provjeru.

Pokretanje: python -m simulator.modbus_pymodbus --modbus-port 5020 --mqtt-host jezgra
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import ModbusTcpServer, StartAsyncTcpServer

from jezgra import konfig
from jezgra.mqtt import Klijent
from jezgra.simulacija import N_DIONICA, Lokacija

SUNSPEC = 40000
A103 = 40070
A124 = A103 + 52
KRAJ = A124 + 26
UPRAVLJANJE = [f"rele_{t}" for t in ("bojler", "pumpa", "uticnice", "hladnjak", "pastir_povrat", "pastir_punjenje")] + \
    [f"ventil_{z}" for z in ("z1", "z2")] + [f"rele_pastir_k{k}" for k in range(1, N_DIONICA + 1)] + ["pastir_snaga"]


def f32(v: float) -> list[int]:
    return list(struct.unpack(">HH", struct.pack(">f", float(v))))


class PraceniBlok(ModbusSequentialDataBlock):
    """Blok koji javlja upise s mreže (od jezgre); interni upisi idu kroz `postavi`."""

    def __init__(self, adresa: int, vrijednosti: list[int], pri_upisu=None):
        super().__init__(adresa, vrijednosti)
        self.pri_upisu = pri_upisu

    def setValues(self, address, values):  # noqa: N802 (API pymodbusa)
        super().setValues(address, values)
        if self.pri_upisu:
            self.pri_upisu(address - 1, values if isinstance(values, list) else [values])

    def postavi(self, adresa_protokola: int, vrijednosti: list[int]) -> None:
        # pymodbus 3.8: protokolna adresa A = adresa bloka A+1
        ModbusSequentialDataBlock.setValues(self, adresa_protokola + 1, vrijednosti)


class Farma:
    def __init__(self, brzina: float = 60.0, sjeme: int = 7, kvarovi: bool = True):
        self.cfg = konfig.ucitaj("/nepostojece")  # zadane postavke
        self.brzina = brzina
        self.lok = Lokacija(self.cfg, time.time(), sjeme=sjeme, kvarovi=kvarovi)
        self.uvoz_kwh = self.izvoz_kwh = 0.0
        self.upisi_jezgre: list[dict] = []
        self.mqtt_naredbe: list[dict] = []
        self._lock = threading.Lock()
        n = KRAJ - SUNSPEC + 4
        self.hr1 = PraceniBlok(SUNSPEC + 1, [0] * n, pri_upisu=self._upis_izmjenjivac)
        self.ir2 = PraceniBlok(1, [0] * 0x60)
        self.hr2 = PraceniBlok(1, [0] * 4)
        self._sunspec_kostur()
        self.kontekst = ModbusServerContext(slaves={
            1: ModbusSlaveContext(hr=self.hr1, ir=ModbusSequentialDataBlock(1, [0] * 4)),
            2: ModbusSlaveContext(ir=self.ir2, hr=self.hr2),
        }, single=False)
        self.osvjezi_registre()

    def _sunspec_kostur(self) -> None:
        r = self.hr1
        r.postavi(SUNSPEC, [0x5375, 0x6E53, 1, 66])
        ime = b"EnergijaSim-pymodbus".ljust(32, b"\0")
        r.postavi(SUNSPEC + 4, [int.from_bytes(ime[i:i + 2], "big") for i in range(0, 32, 2)])
        r.postavi(A103, [103, 50])
        r.postavi(A124, [124, 24])
        r.postavi(A124 + 2, [3000])            # WChaMax 3000 W, SF 0
        r.postavi(A124 + 18, [0])              # WChaMax_SF
        r.postavi(A124 + 22, [0x10000 - 1])    # ChaState_SF = -1 (0,1 %)
        r.postavi(A124 + 24, [0x10000 - 2])    # InBatV_SF = -2
        r.postavi(A124 + 25, [0])              # InOutWRte_SF
        r.postavi(KRAJ, [0xFFFF, 0])

    def osvjezi_registre(self) -> None:
        with self._lock:
            o = self.lok.ocitanja()
            self.hr1.postavi(A103 + 14, [int(o["pv_snaga_w"]) & 0xFFFF, 0])
            self.hr1.postavi(A124 + 8, [int(o["baterija_soc"] * 1000)])
            self.hr1.postavi(A124 + 10, [int(o["baterija_napon_v"] * 100)])
            m = self.lok.mreza_w
            vals = [0] * 0x60
            for adr, v in ((0x00, 230.0 + (m / 2000)), (0x34, m), (0x46, 50.0), (0x48, self.uvoz_kwh),
                           (0x4A, self.izvoz_kwh)):
                vals[adr:adr + 2] = f32(v)
            self.ir2.postavi(0, vals)

    def _upis_izmjenjivac(self, adresa: int, vrijednosti: list[int]) -> None:
        """Upis jezgre: StorCtl_Mod (A124+5), OutWRte (A124+12), InWRte (A124+13)."""
        regs = {adresa + i: v for i, v in enumerate(vrijednosti)}
        self.upisi_jezgre.append({"t": time.time(), "adresa": adresa, "vrijednosti": vrijednosti})
        del self.upisi_jezgre[:-50]
        if not any(A124 + 5 <= a <= A124 + 13 for a in regs):
            return
        procitaj = lambda a: self.hr1.getValues(a + 1, 1)[0]  # noqa: E731
        mod = procitaj(A124 + 5)
        if mod == 0:
            self.lok.postavi("baterija_auto", 1)
        elif procitaj(A124 + 12) == 0 and procitaj(A124 + 13) == 0:
            self.lok.postavi("baterija_ogranicenje", mod)  # samo ograničenje smjera, vlastiti način
        else:
            snaga = 3000 * procitaj(A124 + 13) / 100 - 3000 * procitaj(A124 + 12) / 100
            self.lok.postavi("baterija_snaga_w", snaga)

    def korak(self, dt_stvarno: float) -> None:
        with self._lock:
            dt = dt_stvarno * self.brzina
            self.lok.korak(dt)
            m = self.lok.mreza_w
            self.uvoz_kwh += max(0.0, m) * dt / 3.6e6
            self.izvoz_kwh += max(0.0, -m) * dt / 3.6e6
        self.osvjezi_registre()

    def stanje(self) -> dict:
        l = self.lok
        return {"naredba_bat": l.naredba_bat, "ogranicenje": l.ogranicenje, "releji": l.releji, "ventili": l.ventili, "soc": l.soc,
                "pastir_sklopke": l.pastir_sklopke, "pastir_povrat": l.pastir_povrat, "pastir_snaga": l.pastir_snaga,
                "upisi_jezgre": self.upisi_jezgre[-10:], "mqtt_naredbe": self.mqtt_naredbe[-20:],
                "sim_vrijeme": l.t}


class MqttMost:
    def __init__(self, farma: Farma, host: str, port: int):
        self.f = farma
        self.k = Klijent("sim-farma", host=host, port=port)
        self.k.pri_poruci = self._naredba
        self.k.pokreni()
        self.k.pretplati("sim/+/set")
        o = farma.lok.ocitanja()
        kanali = {k: {"tema": f"sim/{k}"} for k in o if k.startswith(("tlo_", "pastir_", "pumpa_", "bojler_",
                                                                      "potrosnja", "baterija_temp", "baterija_struja",
                                                                      "okolina"))}
        self.najava = json.dumps({"id": "sim-farma", "tip": "farma", "kanali": kanali,
                                  "upravljanje": {k: {"tema": f"sim/{k}/set"} for k in UPRAVLJANJE}})
        self._najavljeno = False

    def _naredba(self, tema: str, poruka: bytes) -> None:
        kanal = tema.split("/")[1]
        txt = poruka.decode().strip().upper()
        v = 1.0 if txt == "ON" else 0.0 if txt == "OFF" else float(txt)
        self.f.mqtt_naredbe.append({"t": time.time(), "kanal": kanal, "v": v})
        del self.f.mqtt_naredbe[:-50]
        with self.f._lock:
            self.f.lok.postavi(kanal, v)

    def objavi(self) -> None:
        if not self.k.spojen.is_set():
            self._najavljeno = False
            return
        if not self._najavljeno:  # nakon (ponovnog) spajanja: zadržana najava za plug-and-play
            self._najavljeno = self.k.objavi("energija/otkrij/sim-farma", self.najava, zadrzi=True)
        for k, v in self.f.lok.ocitanja().items():
            if k.startswith(("tlo_", "pastir_", "pumpa_", "bojler_", "potrosnja", "baterija_temp", "baterija_struja",
                             "okolina")):
                self.k.objavi(f"sim/{k}", json.dumps(v))


def http_stanje(farma: Farma, port: int) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            b = json.dumps(farma.stanje(), default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


async def pokreni(farma: Farma, host: str, modbus_port: int, mqtt: MqttMost | None, period: float = 1.0) -> None:
    async def petlja():
        zadnje = time.monotonic()
        while True:
            await asyncio.sleep(period)
            sada = time.monotonic()
            farma.korak(sada - zadnje)
            zadnje = sada
            if mqtt:
                mqtt.objavi()

    asyncio.get_running_loop().create_task(petlja())
    await StartAsyncTcpServer(context=farma.kontekst, address=(host, modbus_port))


class PosluziteljUNiti:
    """Za testove: vlastita instanca pymodbus poslužitelja u pozadinskoj niti, s urednim gašenjem."""

    def __init__(self, farma: Farma, port: int, host: str = "127.0.0.1"):
        self.farma, self.port, self.host = farma, port, host
        self.petlja: asyncio.AbstractEventLoop | None = None
        self.srv: ModbusTcpServer | None = None
        spreman = threading.Event()

        async def radi():
            self.petlja = asyncio.get_running_loop()
            self.srv = ModbusTcpServer(context=farma.kontekst, address=(host, port))
            spreman.set()
            await self.srv.serve_forever()

        self.nit = threading.Thread(target=lambda: asyncio.run(radi()), daemon=True)
        self.nit.start()
        spreman.wait(5)

    def zaustavi(self) -> None:
        if self.petlja and self.srv:
            asyncio.run_coroutine_threadsafe(self.srv.shutdown(), self.petlja).result(5)
        self.nit.join(5)

    def join(self, timeout: float | None = None) -> None:
        self.nit.join(timeout)


def u_niti(farma: Farma, port: int, host: str = "127.0.0.1") -> PosluziteljUNiti:
    return PosluziteljUNiti(farma, port, host)


def main() -> None:
    ap = argparse.ArgumentParser(description="Simulirana farma: pymodbus + MQTT")
    ap.add_argument("--modbus-port", type=int, default=5020)
    ap.add_argument("--mqtt-host", default="127.0.0.1")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--http-port", type=int, default=8081)
    ap.add_argument("--brzina", type=float, default=60.0)
    ap.add_argument("--bez-kvarova", action="store_true")
    a = ap.parse_args()
    import signal
    import sys
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # uredno gašenje u kontejneru (bez SIGKILL-a)
    farma = Farma(a.brzina, kvarovi=not a.bez_kvarova)
    mqtt = MqttMost(farma, a.mqtt_host, a.mqtt_port)
    http_stanje(farma, a.http_port)
    print(f"Simulator: Modbus TCP :{a.modbus_port} (jedinice 1 SunSpec, 2 SDM), MQTT -> {a.mqtt_host}:{a.mqtt_port}, "
          f"stanje http :{a.http_port}", flush=True)
    asyncio.run(pokreni(farma, "0.0.0.0", a.modbus_port, mqtt))


if __name__ == "__main__":
    main()
