"""Objava stanja na lokalni MQTT broker za kućnu automatiku i pametnu mrežu.

- `energija/stanje/<kljuc>` (zadržano): pv_w, potrosnja_w, mreza_w, baterija_w, baterija_soc, bojler_temp_c,
  cijena_eur_kwh, pastir (način), usteda_mjesec_eur, ... – svakih 30 s (u štednom načinu rjeđe).
- Home Assistant MQTT discovery (`homeassistant/sensor/energija_<id>/<kljuc>/config`, zadržano): HA sam prepozna
  senzore s jedinicama i klasama uređaja – bez ručnog podešavanja.
- `energija/naredbe/topla_voda` (ON): ista naredba kao "Zagrij vodu odmah" (60 min), za automatizacije u HA.
"""
from __future__ import annotations

import json

from . import api_v1

SENZORI = {  # kljuc: (naziv, jedinica, device_class, state_class)
    "pv_w": ("Sunčani paneli", "W", "power", "measurement"),
    "potrosnja_w": ("Potrošnja", "W", "power", "measurement"),
    "mreza_w": ("Mreža", "W", "power", "measurement"),
    "baterija_w": ("Baterija snaga", "W", "power", "measurement"),
    "baterija_soc": ("Baterija", "%", "battery", "measurement"),
    "bojler_temp_c": ("Bojler", "°C", "temperature", "measurement"),
    "cijena_eur_kwh": ("Cijena struje", "EUR/kWh", "monetary", None),
    "usteda_mjesec_eur": ("Ušteda ovaj mjesec", "EUR", "monetary", "total"),
    "pastir": ("Električni pastir", None, None, None),
}


class MqttIntegracija:
    def __init__(self, jezgra, klijent):
        self.j, self.k = jezgra, klijent
        self.id = jezgra.trezor.id_uredaja()[:12]
        self._najavljeno = False
        klijent.pretplati("energija/naredbe/#")

    def najavi(self) -> None:
        uredaj = {"identifiers": [f"energija_{self.id}"], "name": f"Energija – {self.j.cfg['lokacija']['naziv']}",
                  "manufacturer": "Energija (lokalna jezgra)"}
        for k, (naziv, jed, klasa, st) in SENZORI.items():
            cfg = {"name": naziv, "unique_id": f"energija_{self.id}_{k}", "state_topic": f"energija/stanje/{k}",
                   "device": uredaj}
            if jed:
                cfg["unit_of_measurement"] = jed
            if klasa:
                cfg["device_class"] = klasa
            if st:
                cfg["state_class"] = st
            self.k.objavi(f"homeassistant/sensor/energija_{self.id}/{k}/config", json.dumps(cfg), zadrzi=True)
        self.k.objavi(f"homeassistant/button/energija_{self.id}/topla_voda/config", json.dumps({
            "name": "Zagrij vodu odmah", "unique_id": f"energija_{self.id}_topla_voda",
            "command_topic": "energija/naredbe/topla_voda", "payload_press": "ON", "device": uredaj}), zadrzi=True)
        self._najavljeno = True

    def objavi(self) -> None:
        if not self.k.spojen.is_set():
            self._najavljeno = False
            return
        if not self._najavljeno:
            self.najavi()
        t = api_v1.tok(self.j)
        o = self.j.zadnje_ocitanje or {}
        u = (self.j.usteda(self.j.sat()).get("mjesec") or {})
        vrijednosti = {"pv_w": t["pv_w"], "potrosnja_w": t["potrosnja_w"], "mreza_w": t["mreza_w"],
                       "baterija_w": t["baterija_w"],
                       "baterija_soc": None if t["baterija_soc"] is None else round(t["baterija_soc"] * 100, 1),
                       "bojler_temp_c": o.get("bojler_temp_c"), "cijena_eur_kwh": self.j.tarife.cijena(self.j.sat())["kupnja"],
                       "usteda_mjesec_eur": u.get("usteda_eur"), "pastir": self.j.pastir.nacin}
        for k, v in vrijednosti.items():
            if v is not None:
                self.k.objavi(f"energija/stanje/{k}", str(v), zadrzi=True)

    def poruka(self, tema: str, sadrzaj: bytes) -> bool:
        if tema == "energija/naredbe/topla_voda" and sadrzaj.strip().upper() in (b"ON", b"PRESS", b"1"):
            self.j.rucno["bojler"] = (True, self.j.sat() + 3600)
            self.j._dogadjaj("naredba", {"poruka": "MQTT/Home Assistant: topla voda odmah (60 min)"})
            return True
        return False
