"""Katalog scenarija. Svaki scenarij je deklarativan: vrijeme, tarifa, mreža, ubačeni kvarovi,
ispadi uređaja i mrežnih servisa – i očekivanja (KPI) koja moraju vrijediti da bi prošao.

Kvarovi (u danima od početka): ("kratki", dionica, od, do), ("prekid", dionica, od, do),
("suho", None, od, do), ("vegetacija", stopa_po_danu, od, 99).
Ispadi uređaja: (id_uredaja, od, do) – uređaj ne odgovara (kao Modbus/MQTT istek).
Mreža (HTTP prema Open-Meteo / tarifama): (servis, vrsta, od, do), vrsta: pad | 503 | istek | neispravan.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenarij:
    ime: str
    opis: str
    pocetak: tuple[int, int, int]           # datum (ponedjeljak)
    dani: float = 7.0
    korak_s: float = 120.0
    tarifa: str = "vtnt"                    # vtnt | dinamicka (preko mokanog HTTP-a)
    cijene_profil: str | None = None        # dinamička: skokovi | negativne | volatilne
    mreza: bool = True                      # priključak na elektroenergetsku mrežu
    kvarovi: list = field(default_factory=list)
    ispadi_uredaja: list = field(default_factory=list)
    mreza_kvarovi: list = field(default_factory=list)
    temp_pomak: float = 0.0
    starenje: float | None = None           # Ω/dan rast unutarnjeg otpora baterije
    soc0: float = 0.55
    vlaga0: float | None = None             # početna vlaga tla (%) u svim zonama
    povijest: str | None = None             # put do povijesnih podataka (stres/povijest.py): stvarno vrijeme i cijene
    ocekivanja: dict = field(default_factory=dict)
    oznake: tuple = ()


OGRADA_TIPICNO = [("kratki", 3, 1.4, 1.55), ("prekid", 2, 3.3, 3.5), ("vegetacija", 0.008, 2.0, 99)]

KATALOG: list[Scenarij] = [
    Scenarij("proljece_osnovno", "Vikendica u proljeće, VT/NT, tipični kvarovi ograde i rad pumpe na suho",
             (2026, 3, 16), kvarovi=OGRADA_TIPICNO,
             ocekivanja={"usteda_min_udio": -0.02, "pastir_dostupnost_min": 0.95, "izolacija_max_min": 20},
             oznake=("brzi", "ucenje")),
    Scenarij("bunar_presusio", "Ljeto, suho tlo, bunar presuši u jutro zalijevanja: pumpa ne smije raditi na suho",
             (2026, 7, 6), dani=2, korak_s=60, vlaga0=22.0, kvarovi=[("suho", None, 0.0, 1.5)],
             ocekivanja={"suho_reakcija_max_koraka": 2, "zastita_pumpe": True}, oznake=("brzi",)),
    Scenarij("zima_dinamicka", "Zima, dinamička satna tarifa preko (mokanog) HTTP izvora",
             (2026, 1, 12), tarifa="dinamicka", kvarovi=OGRADA_TIPICNO,
             ocekivanja={"usteda_min_udio": 0.10, "pastir_dostupnost_min": 0.95, "tarifa_izvor": "dinamicka"},
             oznake=("brzi", "ucenje")),
    Scenarij("jesen_vtnt", "Jesen, VT/NT, bez kvarova (čisti učinak optimizacije)",
             (2026, 10, 12), ocekivanja={"usteda_min_udio": 0.0}, oznake=("ucenje",)),
    Scenarij("ljeto_otocno", "Ljeto bez mreže: samo sunce i baterija",
             (2026, 7, 6), mreza=False, kvarovi=OGRADA_TIPICNO,
             ocekivanja={"neisporuceno_max_kwh": 0.0, "pastir_dostupnost_min": 0.95}, oznake=("brzi",)),
    Scenarij("zima_otocno_hladno", "Zima bez mreže, 8 °C hladnije od prosjeka: niska baterija, mraz",
             (2026, 1, 12), mreza=False, temp_pomak=-8.0, soc0=0.35,
             ocekivanja={"pastir_dostupnost_min": 0.95}),
    Scenarij("ispad_izmjenjivaca", "Izmjenjivač (Modbus) ne odgovara 6 h, senzori tla 3 h",
             (2026, 3, 16), dani=3,
             ispadi_uredaja=[("sim-izmjenjivac", 1.0, 1.25), ("sim-tlo", 1.5, 1.625)],
             ocekivanja={"uredaj_oporavak": True}, oznake=("brzi",)),
    Scenarij("openmeteo_ispadi", "Open-Meteo: pad mreže, zatim HTTP 503, istek i neispravan JSON",
             (2026, 6, 1), dani=5,
             mreza_kvarovi=[("prognoza", "pad", 0.0, 1.0), ("prognoza", "503", 1.0, 2.0),
                            ("prognoza", "istek", 2.0, 2.5), ("prognoza", "neispravan", 2.5, 3.0)],
             ocekivanja={"prognoza_oporavak": True, "prognoza_zamjena": True}, oznake=("brzi",)),
    Scenarij("visestruki_kvarovi_ograde", "Tri kvara ograde u nizu (dionice 1, 4, 3), uz vegetaciju",
             (2026, 5, 4), dani=4,
             kvarovi=[("kratki", 1, 0.5, 0.6), ("kratki", 4, 1.5, 1.6), ("prekid", 3, 2.5, 2.7),
                      ("vegetacija", 0.006, 0.0, 99)],
             ocekivanja={"pastir_dostupnost_min": 0.93, "izolacija_max_min": 20, "izolacija_min_broj": 2},
             oznake=("brzi",)),
    Scenarij("starenje_baterije", "Baterija ubrzano stari: prediktivno održavanje mora upozoriti",
             (2026, 4, 6), dani=11, korak_s=60, starenje=0.004,
             ocekivanja={"odrzavanje_pokazatelj": "baterija_otpor_mohm"}),
]

# Ekstremni vremenski i cjenovni uvjeti (oznaka "ekstremno"); očekivanja su sigurnosna – ušteda se
# uspoređuje s referentnim strategijama u scenariji/usporedba.py.
SIGURNO = {"pastir_dostupnost_min": 0.93}
KATALOG += [
    Scenarij("toplinski_val", "Toplinski val (+9 °C), suho tlo, večernji cjenovni skokovi", (2026, 7, 20), dani=5,
             temp_pomak=9.0, vlaga0=25.0, tarifa="dinamicka", cijene_profil="skokovi",
             kvarovi=[("vegetacija", 0.006, 0.0, 99)], ocekivanja=dict(SIGURNO), oznake=("ekstremno",)),
    Scenarij("hladni_val", "Hladni val (−12 °C), električno grijanje, cjenovni skokovi", (2026, 1, 19), dani=5,
             temp_pomak=-12.0, tarifa="dinamicka", cijene_profil="skokovi", ocekivanja=dict(SIGURNO),
             oznake=("ekstremno",)),
    Scenarij("tjedan_bez_sunca", "Tjedan guste naoblake (najavljeno), VT/NT", (2026, 11, 16),
             kvarovi=[("oblacno", 0.95, 0.0, 7.0)], ocekivanja=dict(SIGURNO), oznake=("ekstremno",)),
    Scenarij("nenajavljena_naoblaka", "Prognoza kaže sunčano, a oblačno je (pogreška prognoze), dinamička tarifa",
             (2026, 4, 20), dani=5, tarifa="dinamicka", kvarovi=[("nenajavljeno_oblacno", 0.9, 1.0, 4.0)],
             ocekivanja=dict(SIGURNO), oznake=("ekstremno",)),
    Scenarij("oluja_ispad_mreze", "Oluja: ispad mreže 12 h noću, grana na ogradi, kiša", (2026, 6, 8), dani=4,
             kvarovi=[("mreza_ispad", None, 1.75, 2.25), ("kratki", 2, 1.8, 2.0), ("oblacno", 0.9, 1.5, 2.5)],
             ocekivanja={"pastir_dostupnost_min": 0.93, "neisporuceno_max_kwh": 0.0}, oznake=("ekstremno",)),
    Scenarij("negativne_cijene", "Sunčani svibanj s negativnim podnevnim cijenama", (2026, 5, 11), dani=5,
             tarifa="dinamicka", cijene_profil="negativne", ocekivanja=dict(SIGURNO), oznake=("ekstremno",)),
    Scenarij("volatilne_cijene", "Vrlo nestabilne satne cijene (0,3–2,5× i povremeno negativne)", (2026, 3, 2),
             dani=5, tarifa="dinamicka", cijene_profil="volatilne", ocekivanja=dict(SIGURNO), oznake=("ekstremno",)),
    Scenarij("sve_odjednom", "Hladni val + ispad mreže + pogrešna prognoza + pad Open-Meteo + ispad izmjenjivača",
             (2026, 2, 2), dani=4, temp_pomak=-10.0, tarifa="dinamicka", cijene_profil="skokovi",
             kvarovi=[("mreza_ispad", None, 1.8, 2.1), ("nenajavljeno_oblacno", 0.9, 0.5, 3.0), ("kratki", 4, 2.5, 2.6)],
             ispadi_uredaja=[("sim-izmjenjivac", 3.0, 3.1)], mreza_kvarovi=[("prognoza", "pad", 1.0, 2.5)],
             ocekivanja={"pastir_dostupnost_min": 0.93, "uredaj_oporavak": True}, oznake=("ekstremno",)),
]

# Skup za provjeru učenja politike: drugi tjedni (drugo vrijeme), isti tipovi lokacija.
PROVJERA_UCENJA: list[Scenarij] = [
    Scenarij("val_zima_dinamicka", "Provjera: drugi zimski tjedan, dinamička tarifa", (2026, 2, 9), tarifa="dinamicka"),
    Scenarij("val_proljece", "Provjera: drugi proljetni tjedan, VT/NT", (2026, 4, 13)),
    Scenarij("val_jesen", "Provjera: kasna jesen, VT/NT", (2026, 11, 9)),
]


def po_imenu(ime: str) -> Scenarij:
    import os
    if ime.startswith("stres_") and os.environ.get("ENERGIJA_POVIJEST"):
        from stres.povijest import scenariji as stres_scenariji
        for s in stres_scenariji(os.environ["ENERGIJA_POVIJEST"]):
            if s.ime == ime:
                return s
    for s in KATALOG + PROVJERA_UCENJA + EVALUACIJA + EVALUACIJA_2 + RAZVOJ_DINAMICKA:
        if s.ime == ime:
            return s
    raise KeyError(ime)


# ---------------------------------------------------------------------------------------------
# NEOVISNI SKUP ZA OCJENU (zadan 13.11.2026. prije poboljšanja algoritma; na njemu se ne razvija).
# 26 tjedana kroz 2027. (svaki drugi ponedjeljak), naizmjence VT/NT i dinamička tarifa, bez kvarova.
# Pokreće se jednom, na kraju: python -m scenariji.usporedba --skup evaluacija
def _evaluacija(godina: int = 2027, prvi_ponedjeljak: tuple = (1, 4), prefiks: str = "eval") -> list[Scenarij]:
    import datetime as _dt
    out, d = [], _dt.date(godina, *prvi_ponedjeljak)  # bez preklapanja s razvojnim scenarijima (2026.)
    for i in range(26):
        tarifa = "dinamicka" if i % 2 else "vtnt"
        out.append(Scenarij(f"{prefiks}_{d.isoformat()}_{tarifa}", f"Ocjena: tjedan od {d.isoformat()}, {tarifa}",
                            (d.year, d.month, d.day), tarifa=tarifa, oznake=("evaluacija",)))
        d += _dt.timedelta(days=14)
    return out


EVALUACIJA: list[Scenarij] = _evaluacija()  # 1. ocjena – ISKORIŠTENA 13.11.2026. (rezultati/evaluacija/)

# 2. neovisni skup (zadan 13.11.2026., odmah nakon 1. ocjene i PRIJE poboljšanja): 2028., isti raspored.
EVALUACIJA_2: list[Scenarij] = _evaluacija(2028, (1, 3), "eval2")

# Razvojni tjedni s običnom dinamičkom tarifom (2026.) – na njima se smije razvijati.
RAZVOJ_DINAMICKA: list[Scenarij] = [
    Scenarij(f"dev_dinamicka_{m:02d}", f"Razvoj: obična dinamička tarifa, 2026-{m:02d}", p, tarifa="dinamicka",
             oznake=("razvoj_dinamicka",))
    for m, p in ((1, (2026, 1, 26)), (3, (2026, 3, 9)), (5, (2026, 5, 25)), (7, (2026, 7, 13)),
                 (8, (2026, 8, 24)), (10, (2026, 10, 26)), (11, (2026, 11, 30)))]
