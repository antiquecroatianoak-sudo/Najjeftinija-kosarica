"""Registar uređaja u radu: spaja otkrivanje (MQTT najave, Modbus skeniranje, UDP) s jezgrom."""
from __future__ import annotations

import threading
import time

from .mqtt import Klijent
from .otkrivanje import MqttUredaj, iz_najave, lokalne_mreze, nadji_otvorene, skeniraj_modbus


class Registar:
    def __init__(self, jezgra, broker, cfg: dict):
        self.j = jezgra
        self.cfg = cfg
        self.hostovi: set[tuple[str, int]] = {tuple(h) for h in cfg["otkrivanje"]["modbus_hostovi"]}
        self._lock = threading.Lock()
        self._zadnje_trazenje = 0.0
        self.zadnje_skeniranje: dict = {}
        self.mqtt = Klijent(f"jezgra-{jezgra.trezor.id_uredaja()[:8]}", port=broker.port)
        self.mqtt.pri_poruci = self._poruka

    def pokreni(self) -> "Registar":
        self.mqtt.pokreni()
        self.mqtt.spojen.wait(5)
        self.mqtt.pretplati("#")  # lokalni broker: sve teme (najave + stanja)
        threading.Thread(target=self.skeniraj, daemon=True).start()
        return self

    def _dodaj(self, u) -> None:
        with self._lock:
            if any(x.id == u.id for x in self.j.uredaji):
                return
            self.j.uredaji.append(u)
        self.j._dogadjaj("uredaj", {"poruka": f"Prepoznat uređaj {u.id} ({u.tip}, {u.protokol})", **u.opis()})

    def _poruka(self, tema: str, poruka: bytes) -> None:
        integ = getattr(self, "integracija", None)
        if integ and integ.poruka(tema, poruka):
            return
        if tema.startswith(("energija/stanje/", "homeassistant/sensor/energija_", "homeassistant/button/energija_")):
            return  # vlastite objave jezgre nisu uređaji
        if tema.startswith(("energija/otkrij/", "homeassistant/")) and tema.endswith(("config",)) or \
                tema.startswith("energija/otkrij/"):
            u = iz_najave(tema, poruka, self.mqtt.objavi)
            if u:
                self._dodaj(u)
            return
        for u in list(self.j.uredaji):
            if isinstance(u, MqttUredaj):
                u.primi(tema, poruka)

    def uredjaj_najavljen(self, adresa: str, podaci: dict) -> None:
        if "modbus" in podaci:
            self.hostovi.add((adresa, int(podaci["modbus"])))

    def _poznati(self) -> set:
        return {(u.k.host, u.k.port, u.j) for u in self.j.uredaji if hasattr(u, "k") and hasattr(u, "j")}

    def skeniraj(self) -> dict:
        """Nulta konfiguracija: (1) povremeno potraži Modbus uređaje u lokalnoj mreži, (2) istodobno ispitaj sve
        poznate hostove, (3) preskoči uređaje koji već rade. Vraća sažetak (za dijagnostiku i čarobnjak)."""
        o = self.cfg["otkrivanje"]
        t0 = time.monotonic()
        ima_modbus = any(getattr(u, "protokol", "").startswith("modbus") for u in self.j.uredaji)
        period = o.get("lan_period_s", 6 * 3600) if ima_modbus else 900  # dok ništa ne nađe, traži češće
        novi_hostovi = []
        if o.get("lan_skeniranje", True) and time.monotonic() - self._zadnje_trazenje >= period:
            self._zadnje_trazenje = time.monotonic()
            mreze = lokalne_mreze(o.get("lan_mreze") or None)
            novi_hostovi = [h for h in nadji_otvorene(mreze, tuple(o.get("lan_portovi", (502, 1502))),
                                                      preskoci=self.hostovi) if h not in self.hostovi]
            self.hostovi.update(novi_hostovi)
        nadjeno = skeniraj_modbus(sorted(self.hostovi), o["modbus_jedinice"], poznati=self._poznati())
        for u in nadjeno:
            self._dodaj(u)
        self.zadnje_skeniranje = {"vrijeme": time.time(), "trajanje_s": round(time.monotonic() - t0, 2),
                                  "novi_hostovi": [f"{h}:{p}" for h, p in novi_hostovi],
                                  "novi_uredaji": [u.id for u in nadjeno], "hostova": len(self.hostovi)}
        return self.zadnje_skeniranje
