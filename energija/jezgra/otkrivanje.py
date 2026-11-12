"""Univerzalno automatsko prepoznavanje uređaja (plug-and-play).

Tri puta, bez ikakvog ručnog upisa:
1. UDP multicast najava (239.255.70.70:47070, JSON): jezgra se najavljuje klijentima i
   uređajima; uređaj koji se najavi (npr. Modbus pretvarač) automatski se skenira.
2. MQTT najava na ugrađenom brokeru:
   - vlastiti otvoreni format `energija/otkrij/<id>` (zadržana JSON poruka s kanalima),
   - Home Assistant MQTT discovery (`homeassistant/<vrsta>/<objekt>/config`), pa radi s
     velikim brojem postojećih Tasmota/ESPHome/Zigbee2MQTT uređaja.
3. Modbus TCP skeniranje s otiskom profila: SunSpec (izmjenjivači i baterije većine
   proizvođača) i Eastron SDM brojila.

Svi uređaji izlaze kao `Uredaj` s normaliziranim kanalima (npr. `pv_snaga_w`,
`baterija_soc`, `tlo_z1_vlaga`), pa ostatak jezgre ne zna za protokole.
"""
from __future__ import annotations

import json
import socket
import struct
import threading
import time

from .modbus import ModbusGreska, ModbusKlijent, u_float, u_int16


class Uredaj:
    id = "?"
    tip = "?"
    protokol = "?"

    def citaj(self) -> dict[str, float]:
        return {}

    def postavi(self, kanal: str, vrijednost: float) -> bool:
        return False

    def opis(self) -> dict:
        return {"id": self.id, "tip": self.tip, "protokol": self.protokol}


# ------------------------------------------------------------------ Modbus profili
class SunSpecUredaj(Uredaj):
    protokol = "modbus/sunspec"
    BAZA = 40000

    def __init__(self, klijent: ModbusKlijent, jedinica: int, modeli: dict[int, tuple[int, int]], proizvodjac: str):
        self.k, self.j, self.modeli = klijent, jedinica, modeli
        self.proizvodjac = proizvodjac
        self.id = f"sunspec-{klijent.host}-{klijent.port}-{jedinica}"
        self.tip = "baterija" if 124 in modeli else "izmjenjivac"

    @staticmethod
    def sf(r: int) -> float:
        return 10.0 ** u_int16(r)

    def citaj(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for mid in (101, 102, 103):
            if mid in self.modeli:
                a, _ = self.modeli[mid]
                r = self.k.citaj_holding(self.j, a, 18)
                out["pv_snaga_w"] = u_int16(r[14]) * self.sf(r[15])
        if 124 in self.modeli:
            a, _ = self.modeli[124]
            r = self.k.citaj_holding(self.j, a, 26)
            out["baterija_soc"] = r[8] * self.sf(r[22]) / 100.0
            out["baterija_napon_v"] = r[10] * self.sf(r[24])
        return out

    def postavi(self, kanal: str, vrijednost: float) -> bool:
        if kanal not in ("baterija_snaga_w", "baterija_auto", "baterija_ogranicenje") or 124 not in self.modeli:
            return False
        a, _ = self.modeli[124]
        if kanal == "baterija_auto":  # StorCtl_Mod = 0: izmjenjivač u vlastitom načinu rada
            self.k.upisi_vise(self.j, a + 5, [0])
            return True
        if kanal == "baterija_ogranicenje":  # bitovi StorCtl_Mod uz stopu 0 %: zabrana punjenja/pražnjenja
            self.k.upisi(self.j, a + 12, 0)
            self.k.upisi(self.j, a + 13, 0)
            self.k.upisi_vise(self.j, a + 5, [int(vrijednost) & 3])
            return True
        r = self.k.citaj_holding(self.j, a, 26)
        wmax = max(1.0, r[2] * self.sf(r[18]))
        postotak = int(round(min(100.0, abs(vrijednost) / wmax * 100) / self.sf(r[25])))
        if vrijednost >= 0:   # punjenje
            self.k.upisi_vise(self.j, a + 5, [1])
            self.k.upisi(self.j, a + 13, postotak)
            self.k.upisi(self.j, a + 12, 0)
        else:                 # pražnjenje
            self.k.upisi_vise(self.j, a + 5, [2])
            self.k.upisi(self.j, a + 12, postotak)
            self.k.upisi(self.j, a + 13, 0)
        return True

    def opis(self) -> dict:
        return super().opis() | {"proizvodjac": self.proizvodjac, "modeli": sorted(self.modeli)}


def probaj_sunspec(k: ModbusKlijent, jedinica: int) -> SunSpecUredaj | None:
    try:
        r = k.citaj_holding(jedinica, 40000, 2)
    except (ModbusGreska, ConnectionError):
        return None
    if r != [0x5375, 0x6E53]:  # "SunS"
        return None
    modeli, a = {}, 40002
    proizvodjac = "?"
    for _ in range(20):
        mid, duljina = k.citaj_holding(jedinica, a, 2)
        if mid == 0xFFFF:
            break
        modeli[mid] = (a, duljina)
        if mid == 1:
            regs = k.citaj_holding(jedinica, a + 2, 16)
            proizvodjac = b"".join(struct.pack(">H", x) for x in regs).rstrip(b"\0").decode("ascii", "replace")
        a += duljina + 2
    return SunSpecUredaj(k, jedinica, modeli, proizvodjac)


class SdmBrojilo(Uredaj):
    """Eastron SDM120/SDM630 (input registri, IEEE754 float)."""
    protokol = "modbus/sdm"
    tip = "brojilo"

    def __init__(self, k: ModbusKlijent, jedinica: int):
        self.k, self.j = k, jedinica
        self.id = f"sdm-{k.host}-{k.port}-{jedinica}"

    def citaj(self) -> dict[str, float]:
        p = self.k.citaj_input(self.j, 0x0034, 2)
        e = self.k.citaj_input(self.j, 0x0048, 4)
        return {"mreza_snaga_w": u_float(p), "mreza_uvoz_kwh": u_float(e, 0), "mreza_izvoz_kwh": u_float(e, 2)}


def probaj_sdm(k: ModbusKlijent, jedinica: int) -> SdmBrojilo | None:
    try:
        v = u_float(k.citaj_input(jedinica, 0x0000, 2))
        hz = u_float(k.citaj_input(jedinica, 0x0046, 2))
    except (ModbusGreska, ConnectionError, struct.error):
        return None
    return SdmBrojilo(k, jedinica) if 180 <= v <= 260 and 45 <= hz <= 55 else None


def skeniraj_modbus(hostovi: list[tuple[str, int]], jedinice: list[int]) -> list[Uredaj]:
    nadjeno: list[Uredaj] = []
    for host, port in hostovi:
        k = ModbusKlijent(host, port, timeout=0.8, pokusaja=1)
        try:
            k._spoji()
        except OSError:
            continue
        for j in jedinice:
            u = probaj_sunspec(k, j) or probaj_sdm(k, j)
            if u:
                nadjeno.append(u)
                k = ModbusKlijent(host, port, timeout=1.5)  # svaki uređaj ima svoju vezu
    return nadjeno


# ------------------------------------------------------------------ MQTT uređaji
class MqttUredaj(Uredaj):
    protokol = "mqtt"

    def __init__(self, id_: str, tip: str, kanali: dict[str, str], upravljanje: dict[str, str], objavi):
        self.id, self.tip = id_, tip
        self.kanali = kanali            # kanal -> tema stanja
        self.upravljanje = upravljanje  # kanal -> tema naredbe
        self._objavi = objavi
        self._vrijednosti: dict[str, float] = {}
        self.zadnje = 0.0

    def primi(self, tema: str, poruka: bytes) -> bool:
        pogodak = False
        for kanal, t in self.kanali.items():
            if t == tema:
                try:
                    txt = poruka.decode().strip()
                    v = {"on": 1.0, "off": 0.0, "true": 1.0, "false": 0.0}.get(txt.lower())
                    self._vrijednosti[kanal] = float(v if v is not None else json.loads(txt))
                    self.zadnje = time.time()
                    pogodak = True
                except (ValueError, TypeError):
                    pass
        return pogodak

    def citaj(self) -> dict[str, float]:
        return dict(self._vrijednosti)

    def postavi(self, kanal: str, vrijednost: float) -> bool:
        t = self.upravljanje.get(kanal)
        if not t:
            return False
        return self._objavi(t, "ON" if vrijednost >= 0.5 else "OFF") if kanal.startswith("rele_") else \
            self._objavi(t, json.dumps(vrijednost))

    def opis(self) -> dict:
        return super().opis() | {"kanali": sorted(self.kanali), "upravljanje": sorted(self.upravljanje)}


_HA_KANALI = {"moisture": "vlaga", "voltage": "napon", "temperature": "temp", "power": "snaga_w", "current": "struja_a"}


def iz_najave(tema: str, poruka: bytes, objavi) -> MqttUredaj | None:
    """Vlastita najava ili Home Assistant discovery -> MqttUredaj."""
    try:
        cfg = json.loads(poruka)
    except ValueError:
        return None
    if tema.startswith("energija/otkrij/"):
        return MqttUredaj(cfg["id"], cfg.get("tip", "senzor"),
                          {k: v["tema"] for k, v in cfg.get("kanali", {}).items()},
                          {k: v["tema"] for k, v in cfg.get("upravljanje", {}).items()}, objavi)
    if tema.startswith("homeassistant/"):
        dijelovi = tema.split("/")
        if len(dijelovi) < 4:
            return None
        vrsta, obj = dijelovi[1], dijelovi[-2]
        uid = cfg.get("unique_id", obj)
        kanal = f"{obj}_{_HA_KANALI.get(cfg.get('device_class', ''), 'vrijednost')}"
        if vrsta == "switch":
            return MqttUredaj(f"ha-{uid}", "rele", {f"rele_{obj}": cfg.get("state_topic", "")},
                              {f"rele_{obj}": cfg.get("command_topic", "")}, objavi)
        if vrsta == "sensor" and cfg.get("state_topic"):
            return MqttUredaj(f"ha-{uid}", "senzor", {kanal: cfg["state_topic"]}, {}, objavi)
    return None


# ------------------------------------------------------------------ UDP najava
class Najavljivac:
    """Periodična multicast najava jezgre + slušanje najava uređaja."""

    def __init__(self, podaci: dict, grupa: str = "239.255.70.70", port: int = 47070, period: float = 30.0,
                 pri_uredjaju=None):
        self.podaci, self.grupa, self.port, self.period = podaci, grupa, port, period
        self.pri_uredjaju = pri_uredjaju
        self._radi = False

    def pokreni(self) -> "Najavljivac":
        self._radi = True
        threading.Thread(target=self._salji, daemon=True).start()
        threading.Thread(target=self._slusaj, daemon=True).start()
        return self

    def zaustavi(self) -> None:
        self._radi = False

    def _salji(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)  # samo lokalna mreža
        while self._radi:
            try:
                s.sendto(json.dumps(self.podaci).encode(), (self.grupa, self.port))
            except OSError:
                pass  # nema mreže – jezgra radi i dalje
            time.sleep(self.period)

    def _slusaj(self) -> None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", self.port))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                         socket.inet_aton(self.grupa) + socket.inet_aton("0.0.0.0"))
            s.settimeout(2.0)
        except OSError:
            return
        while self._radi:
            try:
                b, adr = s.recvfrom(4096)
                p = json.loads(b)
                if p.get("usluga") == "energija-uredaj" and self.pri_uredjaju:
                    self.pri_uredjaju(adr[0], p)
            except (socket.timeout, ValueError):
                continue
            except OSError:
                return


def nadji_jezgru(grupa: str = "239.255.70.70", port: int = 47070, timeout: float = 35.0) -> dict | None:
    """Za klijente (aplikacija, tehničar u LAN-u): pričekaj najavu jezgre."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(grupa) + socket.inet_aton("0.0.0.0"))
    s.settimeout(timeout)
    try:
        while True:
            b, adr = s.recvfrom(4096)
            p = json.loads(b)
            if p.get("usluga") == "energija-jezgra":
                return p | {"adresa": adr[0]}
    except (socket.timeout, ValueError):
        return None
    finally:
        s.close()
