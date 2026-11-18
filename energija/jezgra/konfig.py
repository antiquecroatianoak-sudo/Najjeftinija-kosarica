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
                 # (uključeno nakon mjerenja 18.11.2026.: −5,4 % troška na razvojnom katalogu, nijedan scenarij lošiji)
                 "ucenje_pristranosti": True, "pristranost_prag": 0.25, "pristranost_udio": 1.0,
                 # spremnik se planira po graničnim cijenama iz okvirnog plana baterije (dva prolaza)
                 "zajednicko_planiranje": False},
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


# Opis važnih postavki: (jedinica, najmanje, najviše, opis). Vrijednost izvan raspona se odbacuje i ostaje zadana.
# Isti popis koristi `--postavi`, `--dijagnoza` i referenca ULAZI_IZLAZI.md – jedan izvor istine.
OPIS: dict[str, tuple[str, float | None, float | None, str]] = {
    "lokacija.sirina": ("°", -90, 90, "geografska širina (prognoza sunca)"),
    "lokacija.duzina": ("°", -180, 180, "geografska dužina"),
    "baterija.kapacitet_kwh": ("kWh", 0.5, 500, "korisni kapacitet baterije"),
    "baterija.celija_serija": ("", 1, 64, "broj ćelija u seriji (16 = 51,2 V LiFePO4)"),
    "baterija.soc_min": ("0–1", 0.02, 0.9, "ispod ove razine samo kritična trošila"),
    "baterija.soc_kriticno": ("0–1", 0.0, 0.5, "otočno: najniža razina za kritična trošila"),
    "baterija.soc_max": ("0–1", 0.3, 1.0, "gornja razina punjenja"),
    "baterija.max_punjenje_kw": ("kW", 0.1, 100, "najveća snaga punjenja"),
    "baterija.max_praznjenje_kw": ("kW", 0.1, 100, "najveća snaga pražnjenja"),
    "baterija.temp_punjenje_min_c": ("°C", -20, 15, "ispod ove temperature nema punjenja"),
    "baterija.temp_max_c": ("°C", 30, 70, "iznad: preventivno smanjenje opterećenja"),
    "baterija.trosak_ciklusa_eur_kwh": ("€/kWh", 0, 0.5, "procjena trošenja po kWh protoka"),
    "fotonapon.kwp": ("kWp", 0, 200, "vršna snaga panela"),
    "fotonapon.faktor_ucinka": ("0–1", 0.3, 1.0, "gubici sustava (kabeli, prljavština, izmjenjivač)"),
    "mreza.dostupna": ("da/ne", None, None, "postoji li priključak na mrežu"),
    "mreza.max_uvoz_kw": ("kW", 0.5, 200, "priključna snaga"),
    "tarifa.vt_eur_kwh": ("€/kWh", 0, 2, "viša tarifa"),
    "tarifa.nt_eur_kwh": ("€/kWh", 0, 2, "niža tarifa"),
    "tarifa.izvoz_eur_kwh": ("€/kWh", -1, 2, "otkupna cijena"),
    "tarifa.izvor_url": ("URL", None, None, "dinamička satna tarifa (prazno = VT/NT)"),
    "pastir.min_kv": ("kV", 0.5, 15, "ispod: slaba ograda"),
    "pastir.kvar_kv": ("kV", 0.1, 10, "ispod: kratki spoj ili prekid"),
    "navodnjavanje.kisa_preskoci_mm": ("mm", 0, 50, "prognozirana kiša koja preskače zalijevanje"),
    "navodnjavanje.max_minuta": ("min", 1, 240, "najdulje zalijevanje jedne zone"),
    "navodnjavanje.pumpa_kw": ("kW", 0.05, 20, "snaga pumpe"),
    "api.port": ("", 1, 65535, "port HTTPS sučelja"),
    "mqtt.port": ("", 1, 65535, "port lokalnog MQTT brokera"),
    "spremnik.volumen_l": ("l", 10, 2000, "volumen spremnika tople vode"),
    "spremnik.t_min_c": ("°C", 35, 55, "najniža temperatura tople vode"),
    "spremnik.dizalica_kw": ("kW", 0, 10, "električna snaga dizalice topline (0 = nema je)"),
    "spremnik.dt_max_c": ("°C", 40, 65, "najviša temperatura koju postiže dizalica"),
    "spremnik.grijac_kw": ("kW", 0.3, 12, "snaga električnog grijača"),
    "spremnik.grijac_max_c": ("°C", 60, 80, "najviša temperatura grijača"),
    "spremnik.legionela.period_dana": ("dana", 1, 14, "razmak ciklusa protiv legionele"),
    "spremnik.legionela.cilj_c": ("°C", 60, 75, "temperatura ciklusa (najmanje 60 °C)"),
    "otkrivanje.lan_skeniranje": ("da/ne", None, None, "sam traži Modbus uređaje u lokalnoj mreži"),
    "politika.izvoz_iz_baterije": ("da/ne", None, None, "smije li baterija prodavati u mrežu"),
}

def _mreze(v) -> str | None:
    import ipaddress
    for m in v:
        try:
            ipaddress.ip_network(m, strict=False)
        except (TypeError, ValueError):
            return f"neispravna mreža {m!r} (primjer: \"192.168.1.0/24\")"
    return None


def _hostovi(v) -> str | None:
    for h in v:
        if not (isinstance(h, list) and len(h) == 2 and isinstance(h[0], str) and isinstance(h[1], int)
                and 1 <= h[1] <= 65535):
            return f"neispravan host {h!r} (primjer: [\"192.168.1.20\", 502])"
    return None


def _cijeli_portovi(v) -> str | None:
    return None if all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= 65535 for x in v) else \
        "portovi moraju biti cijeli brojevi 1–65535"


def _jedinice(v) -> str | None:
    return None if v and all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 247 for x in v) else \
        "Modbus jedinice: popis cijelih brojeva 0–247"


def _tekstovi(v) -> str | None:
    return None if all(isinstance(x, str) for x in v) else "očekivan popis tekstova"


# provjera sadržaja popisa (tip popisa provjerava se općenito)
SADRZAJ = {"otkrivanje.lan_mreze": _mreze, "otkrivanje.modbus_hostovi": _hostovi,
           "otkrivanje.lan_portovi": _cijeli_portovi, "otkrivanje.modbus_jedinice": _jedinice,
           "api.cors_izvori": _tekstovi, "kopije.odredista": _tekstovi}

# odnosi među postavkama: (uvjet, poruka, ključevi koji se vraćaju na zadano ako uvjet ne vrijedi)
ODNOSI = [
    (lambda c: c["baterija"]["soc_kriticno"] < c["baterija"]["soc_min"] < c["baterija"]["soc_max"],
     "mora vrijediti soc_kriticno < soc_min < soc_max",
     ["baterija.soc_kriticno", "baterija.soc_min", "baterija.soc_max"]),
    (lambda c: c["pastir"]["kvar_kv"] < c["pastir"]["min_kv"], "mora vrijediti pastir.kvar_kv < pastir.min_kv",
     ["pastir.kvar_kv", "pastir.min_kv"]),
    (lambda c: c["spremnik"]["t_min_c"] < c["spremnik"]["grijac_max_c"]
     and c["spremnik"]["legionela"]["cilj_c"] <= c["spremnik"]["grijac_max_c"],
     "mora vrijediti spremnik.t_min_c < grijac_max_c i legionela.cilj_c ≤ grijac_max_c",
     ["spremnik.t_min_c", "spremnik.grijac_max_c", "spremnik.legionela.cilj_c"]),
]


def _dohvati(d: dict, put: str):
    for k in put.split("."):
        d = d[k]
    return d


def _upisi(d: dict, put: str, v) -> None:
    *roditelji, zadnji = put.split(".")
    for k in roditelji:
        d = d[k]
    d[zadnji] = v


def _isti_tip(zadano, v) -> bool:
    if zadano is None:
        return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))
    if isinstance(zadano, bool):
        return isinstance(v, bool)
    if isinstance(zadano, (int, float)):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, type(zadano))


def provjeri(nove: dict, baza: dict | None = None, put: str = "") -> tuple[dict, list[str]]:
    """Provjerava korisničke izmjene prema zadanim postavkama: nepoznati ključ (uz prijedlog), krivi tip i
    vrijednost izvan raspona se odbacuju uz upozorenje. Vraća (prihvaćene izmjene, upozorenja)."""
    import difflib
    baza = ZADANO if baza is None else baza
    ok: dict = {}
    upoz: list[str] = []
    if not isinstance(nove, dict):
        return ok, [f"{put or 'postavke'}: očekivan JSON objekt, dobiveno {type(nove).__name__}"]
    for k, v in nove.items():
        p = f"{put}.{k}" if put else k
        if k.startswith("_"):
            continue
        if k not in baza:
            slicno = difflib.get_close_matches(k, list(baza), n=1, cutoff=0.6)
            upoz.append(f"{p}: nepoznata postavka, zanemarena" + (f" (misli se na '{slicno[0]}'?)" if slicno else ""))
            continue
        z = baza[k]
        if isinstance(z, dict) and z:
            pod, u = provjeri(v, z, p)
            upoz += u
            if pod:  # prazan objekt (sve odbačeno) se ne prenosi
                ok[k] = pod
            continue
        if not _isti_tip(z, v):
            ocekivano = "broj" if isinstance(z, (int, float)) and not isinstance(z, bool) else \
                {bool: "true/false", str: "tekst", list: "popis", dict: "objekt"}.get(type(z), type(z).__name__)
            upoz.append(f"{p}: očekivano {ocekivano}, dobiveno {json.dumps(v, ensure_ascii=False)} – ostaje {z!r}")
            continue
        if p in SADRZAJ and (greska := SADRZAJ[p](v)):
            upoz.append(f"{p}: {greska} – ostaje {z!r}")
            continue
        if p in OPIS and isinstance(v, (int, float)) and not isinstance(v, bool):
            jed, mn, mx, _ = OPIS[p]
            if (mn is not None and v < mn) or (mx is not None and v > mx):
                upoz.append(f"{p}: {v} {jed} izvan raspona {mn}–{mx} – ostaje {z!r}")
                continue
        ok[k] = v
    return ok, upoz


def provjeri_odnose(cfg: dict) -> list[str]:
    """Odnosi među postavkama (npr. soc_min < soc_max). Ako ne vrijede, ti ključevi se vraćaju na zadano."""
    upoz = []
    for uvjet, poruka, kljucevi in ODNOSI:
        if not uvjet(cfg):
            upoz.append(f"{poruka} – vraćeno na zadano: {', '.join(kljucevi)}")
            for k in kljucevi:
                _upisi(cfg, k, copy.deepcopy(_dohvati(ZADANO, k)))
    return upoz


def _putevi(d: dict, put: str = ""):
    for k, v in d.items():
        p = f"{put}.{k}" if put else k
        if isinstance(v, dict) and v:
            yield from _putevi(v, p)
        else:
            yield p


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
    upozorenja: list[str] = []
    p = Path(mapa) / "postavke.json"
    izvori = []
    if p.exists():
        try:
            izvori.append(("postavke.json", json.loads(p.read_text("utf-8"))))
        except (OSError, ValueError) as e:  # nastavi sa zadanim – greška se bilježi
            cfg["_greska_postavki"] = str(e)
    # ENERGIJA_POSTAVKE (JSON u varijabli okoline) – za kontejnere bez montiranja datoteka (npr. CI s Docker-in-Docker)
    if os.environ.get("ENERGIJA_POSTAVKE"):
        try:
            izvori.append(("ENERGIJA_POSTAVKE", json.loads(os.environ["ENERGIJA_POSTAVKE"])))
        except ValueError as e:
            cfg["_greska_postavki"] = f"ENERGIJA_POSTAVKE: {e}"
    zadani_kljucevi: list[str] = []
    for ime, nove in izvori:
        prihvaceno, u = provjeri(nove)
        upozorenja += [f"{ime}: {x}" for x in u]
        _spoji(cfg, prihvaceno)
        zadani_kljucevi += list(_putevi(prihvaceno))
    cfg["_korisnicki_kljucevi"] = sorted(set(zadani_kljucevi))
    upozorenja += provjeri_odnose(cfg)
    if upozorenja:
        cfg["_upozorenja_postavki"] = upozorenja
    return cfg


def korisnicke(mapa: Path) -> dict:
    """Sadržaj postavke.json (samo izmjene u odnosu na zadano); prazno ako datoteke nema ili je neispravna."""
    try:
        v = json.loads((Path(mapa) / "postavke.json").read_text("utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def protumaci(tekst: str):
    """Vrijednost s naredbenog retka: true/false, broj, null, JSON (popis/objekt) ili tekst."""
    t = tekst.strip()
    if t.lower() in ("da", "true", "uključeno", "ukljuceno"):
        return True
    if t.lower() in ("ne", "false", "isključeno", "iskljuceno"):
        return False
    try:
        return json.loads(t.replace(",", ".") if t.count(",") == 1 and t.replace(",", "").replace("-", "").isdigit()
                          else t)
    except ValueError:
        return t


def postavi(mapa: Path, dodjele: list[str]) -> tuple[dict, list[str]]:
    """`kljuc=vrijednost` (npr. baterija.kapacitet_kwh=10) -> provjereno upisano u postavke.json.
    Prečac: `lokacija=45.33,14.44`. Vraća (nove korisničke postavke, upozorenja); ništa neispravno se ne upisuje."""
    izmjene: dict = {}
    greske: list[str] = []
    for d in dodjele:
        kljuc, jednako, vrijednost = d.partition("=")
        kljuc = kljuc.strip()
        if not jednako or not kljuc:
            greske.append(f"'{d}': očekivano kljuc=vrijednost")
            continue
        if kljuc == "lokacija" and vrijednost.count(",") == 1:  # prečac: širina,dužina
            sir, duz = (x.strip() for x in vrijednost.split(","))
            dodjele_lok = {"sirina": protumaci(sir), "duzina": protumaci(duz)}
            _spoji(izmjene, {"lokacija": dodjele_lok})
            continue
        cilj = izmjene
        *roditelji, zadnji = kljuc.split(".")
        for k in roditelji:
            cilj = cilj.setdefault(k, {})
        cilj[zadnji] = protumaci(vrijednost)
    prihvaceno, upoz = provjeri(izmjene)
    upoz = greske + upoz
    nove = _spoji(korisnicke(mapa), prihvaceno)
    probni = _spoji(copy.deepcopy(ZADANO), copy.deepcopy(nove))
    odnosi = provjeri_odnose(probni)
    if odnosi:  # nedosljedan skup se ne upisuje
        return korisnicke(mapa), upoz + odnosi
    if prihvaceno:
        p = Path(mapa) / "postavke.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        privremena = p.with_suffix(".tmp")
        privremena.write_text(json.dumps(nove, indent=2, ensure_ascii=False) + "\n", "utf-8")
        privremena.replace(p)  # atomski: jezgra nikad ne vidi pola datoteke
    return nove, upoz


def podatkovna_mapa() -> Path:
    m = Path(os.environ.get("ENERGIJA_PODACI", Path.home() / ".energija"))
    m.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(m, 0o700)
    except OSError:
        pass
    return m
