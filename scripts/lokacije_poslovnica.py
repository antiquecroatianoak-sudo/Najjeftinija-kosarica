"""
Provjerene koordinate stvarnih poslovnica i popis naselja za odabir lokacije u aplikaciji.

Izvor: OpenStreetMap (© OpenStreetMap suradnici, licenca ODbL), jedan upit Overpass API-ju dnevno za trgovine
lanaca i jedan za naselja. Poslovnica iz službenog cjenika dobiva koordinate samo kad se OSM trgovina istog lanca
poklapa po ulici, kućnom broju i mjestu (ili poštanskom broju); središte grada se nikad ne koristi kao koordinata
poslovnice. Neuparene poslovnice ostaju bez koordinata (aplikacija ih ne smatra poslovnicama unutar kruga).

Zapisuje:
  site/data/lokacije.json          [[lanac, store_id, lat, lon, osm, kvaliteta], ...] (učitava aplikacija)
  site/data/mjesta.json            [[naziv, lat, lon, vrsta, najbliži grad], ...] (prijedlozi pri upisu mjesta)
  site/data/lokacije-izvjesce.json pokrivenost po lancu i trag svakog para (adresa, OSM element, kvaliteta)

Pokretanje:  python scripts/lokacije_poslovnica.py [site/data/proizvodi.json]
"""

import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PODACI = Path(__file__).resolve().parent.parent / "site" / "data"
OVERPASS = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
# Prethodno objavljeni podaci: ako Overpass ne odgovori, zadržavaju se samo raniji parovi s istom adresom.
OBJAVLJENO = "https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/data"
AGENT = "Najjeftinija-kosarica/1.0 (+https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica)"
IZVOR = "© OpenStreetMap suradnici (ODbL), openstreetmap.org/copyright"

# Lanac (ime u aplikaciji) -> nazivi pod kojima je u OSM-u (brand/name/operator), kao nizovi riječi.
NAZIVI_LANCA = {
    "Konzum": ["konzum"], "Lidl": ["lidl"], "Plodine": ["plodine"], "Kaufland": ["kaufland"],
    "Spar": ["spar", "interspar", "eurospar", "despar"], "NTL": ["ntl"], "Studenac": ["studenac"],
    "Tommy": ["tommy"], "KTC": ["ktc"], "Eurospin": ["eurospin"], "Ribola": ["ribola"], "Boso": ["boso"],
    "Trgocentar": ["trgocentar"], "Vrutak": ["vrutak"], "Lorenco": ["lorenco"], "Roto": ["roto", "roto dinamic"],
    "Stridon": ["stridon"], "Branka": ["branka"], "Dukat": ["dukat"], "Jadranka": ["jadranka"], "Bure": ["bure"],
    "Brodokomerc": ["brodokomerc"], "Žabac": ["zabac"], "Djelo Vodice": ["djelo"], "dm": ["dm"],
    "Stanić": ["stanic"], "Trgovina Krk": ["trgovina krk"], "Gavranović": ["gavranovic"], "Metro": ["metro"],
}
# Riječi koje ne razlikuju ulice (vrsta ulice, prijedlozi, kratice).
OPCE = {"ulica", "ul", "cesta", "c", "trg", "put", "obala", "i", "od", "na", "u", "sv", "svetog", "svete", "sveti",
        "svetoga", "dr", "bb", "br", "kbr", "hr", "dio", "odvojak", "prilaz", "naselje", "nas", "set", "setaliste"}
VRSTE_MJESTA = {"city": 0, "town": 1, "village": 2, "suburb": 3, "quarter": 3, "neighbourhood": 4, "hamlet": 5}


def norm(tekst: str) -> str:
    tekst = (tekst or "").replace("đ", "d").replace("Đ", "D")
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", tekst).strip()


def udaljenost_km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = math.radians
    h = math.sin(r(b_lat - a_lat) / 2) ** 2 + math.cos(r(a_lat)) * math.cos(r(b_lat)) * math.sin(r(b_lon - a_lon) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def overpass(upit: str) -> dict:
    zahtjev = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": upit}).encode(),
                                     headers={"User-Agent": AGENT})
    # Najviše dva pokušaja po 240 s (upit sam ima [timeout:240]); kvar se obrađuje zadržavanjem ranijih podataka.
    for pokusaj in range(2):
        try:
            with urllib.request.urlopen(zahtjev, timeout=240) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if pokusaj == 1:
                raise
            time.sleep(30)  # pravila korištenja: bez naglih ponavljanja


def upit_trgovina() -> str:
    rijeci = sorted({r for nazivi in NAZIVI_LANCA.values() for n in nazivi for r in [n.split()[0]]})
    uzorak = "|".join(rijeci).replace("zabac", "[žz]abac").replace("stanic", "stani[cć]").replace("gavranovic", "gavranovi[cć]")
    return (f'[out:json][timeout:240];area["ISO3166-1"="HR"][admin_level=2]->.hr;'
            f'(nwr["shop"]["brand"~"{uzorak}",i](area.hr);nwr["shop"]["name"~"{uzorak}",i](area.hr);'
            f'nwr["shop"]["operator"~"{uzorak}",i](area.hr););out center tags;')


def upit_mjesta() -> str:
    vrste = "|".join(VRSTE_MJESTA)
    return f'[out:json][timeout:240];area["ISO3166-1"="HR"][admin_level=2]->.hr;node["place"~"^({vrste})$"]["name"](area.hr);out;'


# ---------- Uparivanje ----------
def tokeni(tekst: str) -> list[str]:
    return norm(tekst).split()


def brojevi(rijeci: list[str]) -> set[str]:
    """Kućni brojevi iz teksta: "12", "12a", "12 a" -> {"12", "12a"}."""
    rez = set()
    for i, t in enumerate(rijeci):
        m = re.fullmatch(r"(\d{1,4})([a-z]?)", t)
        if m:
            rez.add(m.group(1))
            if m.group(2):
                rez.add(t)
            elif i + 1 < len(rijeci) and re.fullmatch(r"[a-z]", rijeci[i + 1]):
                rez.add(t + rijeci[i + 1])
    return rez


def isti_token(a: str, b: str) -> bool:
    """Jednaki, ili isti korijen dugih riječi (padeži: starcevica / starceviceva)."""
    if a == b:
        return True
    if min(len(a), len(b)) < 5:
        return False
    zajednicko = len(os.path.commonprefix([a, b]))
    return zajednicko >= max(5, min(len(a), len(b)) - 2)


def ulica_odgovara(ulica: str, rijeci: list[str]) -> bool:
    """Sve značajne riječi OSM ulice moraju biti u adresi; najduža točno ili istim korijenom, ostale i kao inicijal."""
    znacajne = [t for t in tokeni(ulica) if t not in OPCE and not t.isdigit()]
    if not znacajne:
        return False
    najduza = max(znacajne, key=len)
    if len(najduza) < 3 or not any(isti_token(najduza, r) for r in rijeci):
        return False
    for t in znacajne:
        if t is najduza:
            continue
        if not any(isti_token(t, r) or (len(r) == 1 and t.startswith(r)) for r in rijeci):
            return False
    return True


def kucni_broj(broj: str) -> list[str]:
    """OSM "12 A", "12a", "12-14", "12;14" -> ["12a"] / ["12", "14"]."""
    rez = []
    for dio in re.split(r"[;,/-]", (broj or "").lower()):
        dio = dio.replace(" ", "")
        if re.fullmatch(r"\d{1,4}[a-z]?", dio):
            rez.append(dio)
    return rez


def niz_u(niz: list[str], rijeci: list[str]) -> bool:
    n = len(niz)
    return n > 0 and any(rijeci[i:i + n] == niz for i in range(len(rijeci) - n + 1))


def lanac_elementa(oznake: dict) -> set[str]:
    rez = set()
    for kljuc in ("brand", "name", "operator", "brand:hr", "name:hr"):
        rijeci = tokeni(oznake.get(kljuc, ""))
        for lanac, nazivi in NAZIVI_LANCA.items():
            if any(niz_u(n.split(), rijeci) for n in nazivi):
                rez.add(lanac)
    return rez


def valjana_koordinata(lat, lon) -> bool:
    """Broj unutar okvira Hrvatske (s malom marginom)."""
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and 42.0 <= lat <= 46.7 and 13.2 <= lon <= 19.6)


def pripremi_osm(elementi: list[dict]) -> dict[str, list[dict]]:
    """Lanac -> OSM trgovine sa središtem; adresa (ulica, kućni broj, mjesto) ako je OSM navodi."""
    po_lancu = defaultdict(list)
    for e in elementi:
        o = e.get("tags", {})
        lat, lon = (e.get("lat"), e.get("lon")) if "lat" in e else (e.get("center", {}).get("lat"), e.get("center", {}).get("lon"))
        ulica = o.get("addr:street") or o.get("addr:place") or ""
        if not valjana_koordinata(lat, lon):
            continue  # nevaljana ili izvan Hrvatske: odbacuje se
        zapis = {"osm": f"{e['type'][0]}{e['id']}", "lat": lat, "lon": lon, "ulica": ulica,
                 "broj": o.get("addr:housenumber", ""), "mjesto": o.get("addr:city", ""),
                 "postanski": re.sub(r"\D", "", o.get("addr:postcode", ""))}
        for lanac in lanac_elementa(o):
            po_lancu[lanac].append(zapis)
    return po_lancu


def indeks_mjesta(mjesta: list[list]) -> dict[str, list[tuple]]:
    """Normalizirani naziv naselja -> [(lat, lon, vrsta)] (gradovi, mjesta, sela)."""
    rez = defaultdict(list)
    for naziv, lat, lon, vrsta, _ in mjesta:
        if vrsta <= 2:
            rez[norm(naziv)].append((lat, lon, vrsta))
    return rez


def naselje_blizu(rijeci: list[str], k: dict, naselja: dict, km: float = 10) -> bool:
    for duljina in (3, 2, 1):
        for i in range(len(rijeci) - duljina + 1):
            if any(udaljenost_km(m[0], m[1], k["lat"], k["lon"]) <= km for m in naselja.get(" ".join(rijeci[i:i + duljina]), [])):
                return True
    return False


def upari_poslovnicu(tekst: str, kandidati: list[dict], naselja: dict) -> tuple[dict | None, str]:
    """(OSM trgovina, kvaliteta) ili (None, razlog). Kvaliteta: "adresa+mjesto", "adresa+postanski", "adresa+blizina"."""
    rijeci = tokeni(tekst)
    broj_u_tekstu = brojevi(rijeci)
    nadjeni = []
    for k in kandidati:
        if not k["ulica"] or not any(b in broj_u_tekstu for b in kucni_broj(k["broj"])) or not ulica_odgovara(k["ulica"], rijeci):
            continue
        if k["postanski"] and len(k["postanski"]) == 5 and k["postanski"] in rijeci:
            nadjeni.append((k, "adresa+postanski"))
        elif k["mjesto"] and niz_u(tokeni(k["mjesto"]), rijeci):
            nadjeni.append((k, "adresa+mjesto"))
        elif naselje_blizu(rijeci, k, naselja):
            # OSM bez mjesta: naselje iz adrese poslovnice mora biti unutar 10 km od trgovine.
            nadjeni.append((k, "adresa+blizina"))
    if not nadjeni:
        return None, "nema OSM trgovine lanca s istom ulicom, brojem i mjestom"
    prvi = nadjeni[0][0]
    if any(udaljenost_km(prvi["lat"], prvi["lon"], k["lat"], k["lon"]) > 0.15 for k, _ in nadjeni[1:]):
        return None, "višeznačno: više različitih OSM trgovina odgovara adresi"
    redoslijed = ["adresa+postanski", "adresa+mjesto", "adresa+blizina"]
    return min(nadjeni, key=lambda x: redoslijed.index(x[1]))


def upari_sve(podaci: dict, osm_po_lancu: dict, naselja: dict, prethodno: dict | None = None) -> tuple[list, dict, list]:
    """(lokacije, pokrivenost po lancu, trag svakog para). `prethodno`: raniji parovi kad OSM nije dostupan."""
    lanci = podaci["lanci"]
    lokacije, trag = [], []
    pokrivenost = defaultdict(Counter)
    parovi = []
    for lanac_idx, store_id, adresa, grad, *_ in podaci["poslovnice"]:
        lanac = lanci[lanac_idx]
        tekst = f"{adresa} {grad}".strip()
        if osm_po_lancu is None:
            raniji = (prethodno or {}).get(f"{lanac}|{store_id}")
            k, kvaliteta = (raniji, raniji["kvaliteta"]) if raniji and raniji.get("adresa") == tekst else (None, "OSM nedostupan")
        else:
            k, kvaliteta = upari_poslovnicu(tekst, osm_po_lancu.get(lanac, []), naselja)
        parovi.append([lanac, store_id, tekst, k, kvaliteta])
    if osm_po_lancu is not None:
        odbij_dijeljene(parovi)
    for lanac, store_id, tekst, k, kvaliteta in parovi:
        pok = pokrivenost[lanac]
        pok["poslovnica"] += 1
        if k is None:
            pok["bez_koordinata"] += 1
            if kvaliteta.startswith("višeznačno"):
                pok["viseznacno"] += 1
            pok[kvaliteta] += 1
            trag.append({"lanac": lanac, "store_id": store_id, "adresa": tekst, "razlog": kvaliteta})
            continue
        pok["s_koordinatama"] += 1
        lat, lon = round(k["lat"], 5), round(k["lon"], 5)
        lokacije.append([lanac, store_id, lat, lon, k["osm"], kvaliteta])
        trag.append({"lanac": lanac, "store_id": store_id, "adresa": tekst, "lat": lat, "lon": lon, "osm": k["osm"],
                     "osm_adresa": f'{k.get("ulica", "")} {k.get("broj", "")}, {k.get("postanski", "")} {k.get("mjesto", "")}'.strip(),
                     "kvaliteta": kvaliteta})
    return lokacije, {l: dict(c) for l, c in sorted(pokrivenost.items())}, trag


def potpis_adrese(tekst: str) -> frozenset:
    """Riječi adrese bez brojeva i oznaka poslovnice (npr. "PJ77-1"): ista adresa pod dva store_id ima isti potpis."""
    return frozenset(t for t in tokeni(tekst) if t.isalpha() and len(t) >= 3)


def odbij_dijeljene(parovi: list[list]) -> None:
    """Ista OSM trgovina uparena s poslovnicama različitih adresa: nijedna ne dobiva koordinate (višeznačno)."""
    po_elementu = defaultdict(list)
    for p in parovi:
        if p[3] is not None:
            po_elementu[p[3]["osm"]].append(p)
    for clanovi in po_elementu.values():
        if len({potpis_adrese(p[2]) for p in clanovi}) > 1:
            for p in clanovi:
                p[3], p[4] = None, "višeznačno: više poslovnica različitih adresa na istoj OSM trgovini"


def sastavi_mjesta(elementi: list[dict]) -> list[list]:
    """[[naziv, lat, lon, vrsta, najbliži grad]] - uz sela i zaseoke najbliži grad, radi razlikovanja istih imena."""
    mjesta = []
    for e in elementi:
        o = e.get("tags", {})
        vrsta = VRSTE_MJESTA.get(o.get("place"))
        if vrsta is None or not o.get("name"):
            continue
        mjesta.append([o.get("name:hr") or o["name"], round(e["lat"], 5), round(e["lon"], 5), vrsta, ""])
    gradovi = [m for m in mjesta if m[3] <= 1]
    for m in mjesta:
        if m[3] >= 2 and gradovi:
            najblizi = min(gradovi, key=lambda g: (g[1] - m[1]) ** 2 + ((g[2] - m[2]) * 0.7) ** 2)
            if najblizi[0] != m[0]:
                m[4] = najblizi[0]
    mjesta.sort(key=lambda m: (m[3], norm(m[0])))
    return mjesta


def dohvati_objavljeno(ime: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(f"{OBJAVLJENO}/{ime}", headers={"User-Agent": AGENT}), timeout=60) as r:
        return json.loads(r.read())


def main():
    ulaz = Path(sys.argv[1]) if len(sys.argv) > 1 else PODACI / "proizvodi.json"
    podaci = json.loads(ulaz.read_text(encoding="utf-8"))
    PODACI.mkdir(parents=True, exist_ok=True)
    sad = datetime.now(timezone.utc).isoformat(timespec="minutes")
    status, osm_datum = "osvježeno iz OpenStreetMapa", sad
    try:
        mjesta = sastavi_mjesta(overpass(upit_mjesta())["elements"])
        time.sleep(5)
        osm_po_lancu = pripremi_osm(overpass(upit_trgovina())["elements"])
        prethodno = None
    except Exception as e:  # noqa: BLE001
        # Kvar osvježavanja ne briše posljednje valjane geopodatke: zadržavaju se objavljeni parovi s istom adresom
        # (novi ili promijenjeni store_id ostaje bez koordinata) i objavljeni popis naselja, uz njihov datum.
        print(f"OpenStreetMap (Overpass) nedostupan: {str(e)[:160]}")
        osm_po_lancu, mjesta, prethodno, osm_datum = None, [], {}, None
        try:
            staro = dohvati_objavljeno("lokacije-izvjesce.json")
            prethodno = {f'{t["lanac"]}|{t["store_id"]}': t for t in staro.get("parovi", []) if "lat" in t}
            osm_datum = staro.get("osm_datum")
        except Exception as e2:  # noqa: BLE001
            print(f"Prethodno izvješće nije dostupno: {str(e2)[:160]}")
        try:
            mjesta = dohvati_objavljeno("mjesta.json")["mjesta"]
        except Exception as e2:  # noqa: BLE001
            print(f"Prethodni popis naselja nije dostupan: {str(e2)[:160]}")
        status = (f"OpenStreetMap nedostupan; zadržani posljednji valjani podaci od {osm_datum}" if osm_datum
                  else "OpenStreetMap nedostupan i nema ranijih valjanih podataka")
    lokacije, pokrivenost, trag = upari_sve(podaci, osm_po_lancu, indeks_mjesta(mjesta), prethodno)
    (PODACI / "lokacije.json").write_text(json.dumps(
        {"izvor": IZVOR, "status": status, "osm_datum": osm_datum, "azurirano": sad, "datum_cjenika": podaci.get("datum"),
         "poslovnice": lokacije}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if mjesta:
        (PODACI / "mjesta.json").write_text(json.dumps({"izvor": IZVOR, "osm_datum": osm_datum, "mjesta": mjesta},
                                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ukupno = sum(p["poslovnica"] for p in pokrivenost.values())
    s_koord = sum(p.get("s_koordinatama", 0) for p in pokrivenost.values())
    izvjesce = {"izvor": IZVOR, "status": status, "osm_datum": osm_datum, "azurirano": sad, "datum_cjenika": podaci.get("datum"),
                "poslovnica": ukupno, "s_koordinatama": s_koord, "bez_koordinata": ukupno - s_koord,
                "viseznacno": sum(p.get("viseznacno", 0) for p in pokrivenost.values()),
                "kvaliteta": dict(Counter(l[5] for l in lokacije)), "lanci": pokrivenost, "parovi": trag}
    (PODACI / "lokacije-izvjesce.json").write_text(json.dumps(izvjesce, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Koordinate poslovnica ({status}): {s_koord} od {ukupno} s pouzdanim koordinatama, {ukupno - s_koord} bez "
          f"(od toga višeznačno {izvjesce['viseznacno']}); naselja za odabir: {len(mjesta)}; izvor: {IZVOR}")
    for lanac, p in pokrivenost.items():
        print(f"  {lanac}: {p.get('s_koordinatama', 0)}/{p['poslovnica']}" + (f", višeznačno {p['viseznacno']}" if p.get("viseznacno") else ""))


if __name__ == "__main__":
    main()
