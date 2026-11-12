"""Registar uređaja u radu: spaja otkrivanje (MQTT najave, Modbus skeniranje, UDP) s jezgrom."""
from __future__ import annotations

import threading

from .mqtt import Klijent
from .otkrivanje import MqttUredaj, iz_najave, skeniraj_modbus


class Registar:
    def __init__(self, jezgra, broker, cfg: dict):
        self.j = jezgra
        self.cfg = cfg
        self.hostovi: set[tuple[str, int]] = {tuple(h) for h in cfg["otkrivanje"]["modbus_hostovi"]}
        self._lock = threading.Lock()
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

    def skeniraj(self) -> None:
        for u in skeniraj_modbus(sorted(self.hostovi), self.cfg["otkrivanje"]["modbus_jedinice"]):
            self._dodaj(u)
