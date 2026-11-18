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
        "soc_kriticno": 0.07,            # otočno: kritična trošila smiju do ove razine (LiFePO4 podnosi)
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
    # cors_izvori: web izvori kojima je dopušteno ugraditi komponente (npr. ["https://portal.example"]); zadano nijedan
    "api": {"port": 8443, "tls": True, "cors_izvori": []},
    "mqtt": {"port": 1883},
    # podesivi parametri politike (zadane vrijednosti; scenariji/ucenje_politike.py ih može predložiti)
    # (trosak_ciklusa_plan: trošenje baterije koje vidi samo planer; None = stvarna procjena iz "baterija")
    # strategija: "pametna" (ova jezgra) ili referentne za usporedbu: "vlastita", "tou", "cjenovni_prag";
    # nadzor_pastira / zastita_pumpe = False glume sustave bez tih funkcija.
    "politika": {"rezerva_dodatak": 0.0, "cuvanje_faktor": 1.0, "trosak_ciklusa_plan": None,
                 "strategija": "pametna", "nadzor_pastira": True, "zastita_pumpe": True,
                 # prodaja energije iz baterije u mrežu pri visokoj izvoznoj cijeni (isključiti ako priključak to ne dopušta)
                 "izvoz_iz_baterije": True,
                 # prag šuma (stabilnost): način rada baterije drži se najmanje min_trajanje_baterija_s (zaštita,
                 # ručne naredbe i zahtjevi mreže djeluju odmah). Mrtva zona cijene je podesiva, ali zadano
                 # isključena: u simulaciji je podizala trošak (vidi STANJE.md, 17.11.2026.). Spremnik vodi MPC.
                 "prag_cijene_eur_kwh": 0.0, "min_trajanje_baterija_s": 900,
                 # kad stvarno sunce trajno odstupa od prognoze: odmah novi plan; korekcija_prognoze: idućih sati
                 # prognoza se množi izmjerenim omjerom (opada prema 1 s vremenskom konstantom korekcija_tau_h)
                 "brzo_preplaniranje": True, "korekcija_prognoze": False, "korekcija_tau_h": 2.0,
                 # sustavna pristranost prognoze sunca (zadnja ~24 h, samo kad je prognoza bila znatna)
                 "ucenje_pristranosti": False, "pristranost_prag": 0.0, "pristranost_udio": 1.0},
    "prognoza": {"url": "https://api.open-meteo.com/v1/forecast"},
    # spremnik PTV-a: model za prediktivno upravljanje (UA se uči iz mjerenja), dizalica topline + grijač, legionela
    "spremnik": {"volumen_l": 150.0, "ua_w_k": 1.5, "t_prostorije_c": 18.0, "t_min_c": 45.0,
                 "dizalica_kw": 0.5, "dt_max_c": 55.0, "grijac_kw": 2.0, "grijac_max_c": 65.0,
                 # ciklički režim protiv legionele: ≥ 60 °C barem drzanje_min, svakih period_dana dana
                 "legionela": {"period_dana": 7.0, "cilj_c": 62.0, "drzanje_min": 30.0, "nadoknada_max_c": 3.0}},
    # lan_skeniranje: sam traži Modbus uređaje u lokalnoj privatnoj mreži (/24 oko vlastite adrese; lan_mreze ih
    # može zadati, npr. ["192.168.1.0/24"]); dok ništa ne nađe svakih 15 min, poslije svakih lan_period_s
    "otkrivanje": {"multicast": "239.255.70.70", "port": 47070, "modbus_hostovi": [], "modbus_jedinice": [1, 2, 3],
                   "lan_skeniranje": True, "lan_mreze": [], "lan_portovi": [502, 1502], "lan_period_s": 21600},
    "trosila": [
        # prioritet: 0 = nikad ne isključivati (pastir), veći broj = ranije isključiti
        {"id": "pastir", "naziv": "Električni pastir", "prioritet": 0, "snaga_w": 8},
        {"id": "hladnjak", "naziv": "Hladnjak", "prioritet": 1, "snaga_w": 90},
        {"id": "pumpa", "naziv": "Pumpa za navodnjavanje", "prioritet": 3, "snaga_w": 750, "fleksibilno": True},
        {"id": "bojler", "naziv": "Grijač spremnika", "prioritet": 4, "snaga_w": 2000, "fleksibilno": True,
         "energija_kwh_dan": 3.0},
        {"id": "dizalica", "naziv": "Dizalica topline (PTV)", "prioritet": 4, "snaga_w": 500, "fleksibilno": True},
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
    # ENERGIJA_POSTAVKE (JSON u varijabli okoline) – za kontejnere bez montiranja datoteka (npr. CI s Docker-in-Docker)
    if os.environ.get("ENERGIJA_POSTAVKE"):
        try:
            _spoji(cfg, json.loads(os.environ["ENERGIJA_POSTAVKE"]))
        except ValueError as e:
            cfg["_greska_postavki"] = f"ENERGIJA_POSTAVKE: {e}"
    return cfg


def podatkovna_mapa() -> Path:
    m = Path(os.environ.get("ENERGIJA_PODACI", Path.home() / ".energija"))
    m.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(m, 0o700)
    except OSError:
        pass
    return m
