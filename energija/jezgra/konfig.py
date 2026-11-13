"""Zadane postavke (nulta konfiguracija).

Korisnik ne mora ništa upisati: sve vrijednosti imaju razumne zadane vrijednosti, a
jezgra ih s vremenom prilagođava (učenje navika, kalibracija brojila, otkrivanje uređaja).
Datoteka `postavke.json` u podatkovnoj mapi smije nadjačati bilo koju vrijednost.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

ZADANO: dict = {
    "lokacija": {"sirina": 45.81, "duzina": 15.98, "naziv": "Vikendica"},  # pretpostavka: kontinentalna Hrvatska
    "baterija": {
        "kemija": "LiFePO4",
        "kapacitet_kwh": 10.0,
        "celija_serija": 16,             # 16s LiFePO4 = 51,2 V nazivno
        "celija_min_v": 2.9,             # radni prag (ne apsolutni minimum 2,5 V) – štedi bateriju
        "celija_max_v": 3.5,             # radni prag ispod 3,65 V – manje trošenja
        "soc_min": 0.15,                 # ispod ovoga samo kritična trošila
        "soc_max": 0.90,                 # ne puniti do 100 % bez potrebe
        "max_punjenje_kw": 3.0,
        "max_praznjenje_kw": 3.0,
        "temp_punjenje_min_c": 0.0,      # LiFePO4 se ne puni ispod 0 °C
        "temp_max_c": 50.0,
        "trosak_ciklusa_eur_kwh": 0.03,  # procjena trošenja po kWh protoka
    },
    "fotonapon": {"kwp": 5.0, "faktor_ucinka": 0.80, "temp_koef": -0.004},
    "mreza": {"dostupna": True, "max_uvoz_kw": 6.9},
    "tarifa": {
        # Pretpostavka (provjeriti s ugovorom): dvotarifni model VT/NT, NT zimi 21–7 h, ljeti 22–8 h.
        "vt_eur_kwh": 0.16, "nt_eur_kwh": 0.08, "izvoz_eur_kwh": 0.05,
        "izvor_url": "", "osvjezi_sati": 6,
    },
    "pastir": {
        "min_kv": 4.0,          # ispod: slaba ograda (vegetacija / odvod)
        "kvar_kv": 1.0,         # ispod: kratki spoj ili prekid
        "ponovni_test_min": 15, # izolirana dionica se periodički ponovno testira
        "eco_snaga": 0.6,       # udio snage u štednom načinu (zdrava ograda)
    },
    "navodnjavanje": {"kisa_preskoci_mm": 3.0, "max_minuta": 45, "pumpa_kw": 0.75},
    "anomalije": {"z_prag": 5.0, "zagrijavanje": 30, "zaglavljen_min": 120},
    "sinkronizacija": {"url": "", "period_s": 900},
    "tunel": {"relej": "", "dopusteno": False},
    "kopije": {"odredista": [], "period_s": 3600, "generacija": 5},
    "izvjestaji": {"co2_kg_kwh": 0.18, "tjedno": True, "mjesecno": True},  # pretpostavka faktora mreže
    "api": {"port": 8443, "tls": True},
    "mqtt": {"port": 1883},
    # podesivi parametri politike (zadane vrijednosti; scenariji/ucenje_politike.py ih može predložiti)
    # (trosak_ciklusa_plan: trošenje baterije koje vidi samo planer; None = stvarna procjena iz "baterija")
    # strategija: "pametna" (ova jezgra) ili referentne za usporedbu: "vlastita", "tou", "cjenovni_prag";
    # nadzor_pastira / zastita_pumpe = False glume sustave bez tih funkcija.
    "politika": {"rezerva_dodatak": 0.0, "cuvanje_faktor": 1.0, "trosak_ciklusa_plan": None,
                 "strategija": "pametna", "nadzor_pastira": True, "zastita_pumpe": True,
                 # prodaja energije iz baterije u mrežu pri visokoj izvoznoj cijeni (isključiti ako priključak to ne dopušta)
                 "izvoz_iz_baterije": True},
    "prognoza": {"url": "https://api.open-meteo.com/v1/forecast"},
    "otkrivanje": {"multicast": "239.255.70.70", "port": 47070, "modbus_hostovi": [], "modbus_jedinice": [1, 2, 3]},
    "trosila": [
        # prioritet: 0 = nikad ne isključivati (pastir), veći broj = ranije isključiti
        {"id": "pastir", "naziv": "Električni pastir", "prioritet": 0, "snaga_w": 8},
        {"id": "hladnjak", "naziv": "Hladnjak", "prioritet": 1, "snaga_w": 90},
        {"id": "pumpa", "naziv": "Pumpa za navodnjavanje", "prioritet": 3, "snaga_w": 750, "fleksibilno": True},
        {"id": "bojler", "naziv": "Bojler", "prioritet": 4, "snaga_w": 2000, "fleksibilno": True,
         "energija_kwh_dan": 3.0},
        {"id": "uticnice", "naziv": "Utičnice", "prioritet": 2, "snaga_w": 0},
    ],
}


def _spoji(baza: dict, nove: dict) -> dict:
    for k, v in nove.items():
        if isinstance(v, dict) and isinstance(baza.get(k), dict):
            _spoji(baza[k], v)
        else:
            baza[k] = v
    return baza


def ucitaj(mapa: Path) -> dict:
    """Zadane postavke + (ako postoji) `postavke.json`. Neispravna datoteka ne ruši jezgru."""
    cfg = copy.deepcopy(ZADANO)
    p = Path(mapa) / "postavke.json"
    if p.exists():
        try:
            _spoji(cfg, json.loads(p.read_text("utf-8")))
        except (OSError, ValueError) as e:  # nastavi sa zadanim – greška se bilježi
            cfg["_greska_postavki"] = str(e)
    return cfg


def podatkovna_mapa() -> Path:
    m = Path(os.environ.get("ENERGIJA_PODACI", Path.home() / ".energija"))
    m.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(m, 0o700)
    except OSError:
        pass
    return m
