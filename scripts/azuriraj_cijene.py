"""
Dnevno preuzimanje cijena iz svih hrvatskih trgovačkih lanaca.

Izvor: javni cjenici koje lanci moraju objavljivati (NN 75/2025), koje
projekt cijene.dev svaki dan skuplja u jednu ZIP arhivu.

Skripta:
  1. preuzme najnoviju arhivu,
  2. za svaki proizvod nađe najnižu valjanu cijenu jedne stvarne poslovnice svakog lanca (uz tu poslovnicu),
  3. spoji iste proizvode iz različitih lanaca (po barkodu) - bez duplikata,
  4. prepozna količinu (g, kg, ml, l, kom) da se može računati cijena po kg/l,
  5. zapiše JSON koji koristi web aplikacija, datoteku po poslovnici (za zbroj popisa u jednoj stvarnoj
     poslovnici) i pokrivenost po lancu (pokrivenost.json).

Pokretanje:  python scripts/azuriraj_cijene.py [put/do/arhive.zip]
"""

import csv
import io
import json
import math
import re
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from array import array
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LIST_URL = "https://api.cijene.dev/v0/list"
# Ručno provjerene količine proizvoda (po barkodu) iz projekta cijene.dev.
DOPUNA_URL = "https://raw.githubusercontent.com/senko/cijene-api/main/enrichment/products.csv"
OUTPUT = Path(__file__).resolve().parent.parent / "site" / "data" / "proizvodi.json"

# Metro je veleprodaja (treba poslovna kartica), pa ga preskačemo.
PRESKOCI_LANCE = {"metro"}

LIJEPA_IMENA = {
    "boso": "Boso", "branka": "Branka", "brodokomerc": "Brodokomerc",
    "bure": "Bure", "djelo_vodice": "Djelo Vodice", "dm": "dm",
    "dukat": "Dukat", "eurospin": "Eurospin", "gavranovic": "Gavranović",
    "jadranka_trgovina": "Jadranka", "kaufland": "Kaufland",
    "konzum": "Konzum", "ktc": "KTC", "lidl": "Lidl", "lorenco": "Lorenco",
    "metro": "Metro", "ntl": "NTL", "plodine": "Plodine", "ribola": "Ribola",
    "roto": "Roto", "spar": "Spar", "stanic": "Stanić", "stridon": "Stridon",
    "studenac": "Studenac", "tommy": "Tommy", "trgocentar": "Trgocentar",
    "trgovina-krk": "Trgovina Krk", "vrutak": "Vrutak", "zabac": "Žabac",
}

# Jedinica -> (osnovna jedinica, faktor). Sve se svodi na kg, l ili kom.
JEDINICE = {
    "mg": ("kg", 0.000001), "g": ("kg", 0.001), "grama": ("kg", 0.001), "gram": ("kg", 0.001), "gr": ("kg", 0.001), "dag": ("kg", 0.01),
    "kg": ("kg", 1),
    "ml": ("l", 0.001), "cl": ("l", 0.01), "dl": ("l", 0.1),
    "l": ("l", 1), "lit": ("l", 1), "litra": ("l", 1), "ltr": ("l", 1),
    "kom": ("kom", 1), "komad": ("kom", 1), "kos": ("kom", 1), "par": ("kom", 1),
    "pak": ("kom", 1), "kut": ("kom", 1),
}
# Razumne granice da pogrešno upisana količina ne pokvari cijenu po kg/l.
NAJVISE = {"kg": 50, "l": 50, "kom": 500}

BROJ = r"(\d+(?:[.,]\d+)?)"
JED = r"(mg|grama|gram|g|gr|dag|kg|ml|cl|dl|l|lit|litra|ltr|kom|komad|kos|par|pak|kut)\b\.?"
# "6x0,5 l", "4 x 125 g"
RE_VISE = re.compile(rf"(\d+)\s*[x×*]\s*{BROJ}\s*{JED}", re.I)
# "125 g x 4", "0,5 l x 6"
RE_VISE_IZA = re.compile(rf"{BROJ}\s*{JED}\s*[x×*]\s*(\d+)(?![.,]?\d)", re.I)
# "500 g", "1,5L"
RE_JEDNO = re.compile(rf"{BROJ}\s*{JED}", re.I)


def preuzmi_najnoviju_arhivu(odrediste: Path) -> str:
    with urllib.request.urlopen(LIST_URL, timeout=60) as r:
        arhive = json.load(r)["archives"]
    najnovija = max(arhive, key=lambda a: a["date"])
    print(f"Preuzimam arhivu za {najnovija['date']} ({najnovija['size'] // 1_000_000} MB)")
    urllib.request.urlretrieve(najnovija["url"], odrediste)
    return najnovija["date"]


def preuzmi_dopunu() -> dict[str, tuple[float, str]]:
    """Barkod -> (količina, jedinica). Ako ne uspije, radimo i bez toga."""
    try:
        with urllib.request.urlopen(DOPUNA_URL, timeout=60) as r:
            redovi = csv.DictReader(io.TextIOWrapper(r, encoding="utf-8"))
            dopuna = {}
            for red in redovi:
                m = mjera(red.get("quantity", ""), red.get("unit", ""))
                if m:
                    dopuna[red["barcode"].strip()] = m
    except Exception as e:  # noqa: BLE001 - dopuna nije obavezna
        print(f"Dopuna količina nije dostupna ({e}), nastavljam bez nje.")
        return {}
    print(f"Dopuna količina: {len(dopuna)} proizvoda")
    return dopuna


def u_broj(vrijednost: str) -> float | None:
    try:
        broj = float(vrijednost.replace(",", "."))
    except (AttributeError, ValueError):
        return None
    return broj if math.isfinite(broj) and broj > 0 else None


def cijena_za_uvoz(vrijednost: str) -> float | None:
    """Odbaci ponude koje bi se prikazale kao 0,00 ili 0,01 EUR."""
    broj = u_broj(vrijednost)
    if broj is None:
        return None
    cijena = round(broj, 2)
    return cijena if cijena > 0.01 else None


def citaj_csv(zf: zipfile.ZipFile, ime: str):
    with zf.open(ime) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))


def normaliziraj(tekst: str) -> str:
    """Isto kao u aplikaciji: "Šećer Kristal" -> "secer kristal"."""
    tekst = tekst.lower().replace("đ", "d")
    tekst = "".join(z for z in unicodedata.normalize("NFD", tekst) if not unicodedata.combining(z))
    return re.sub(r"[^a-z0-9]+", " ", tekst).strip()


def _u_osnovnu(iznos: float, jedinica: str) -> tuple[float, str] | None:
    osnovna = JEDINICE.get(jedinica.lower().rstrip("."))
    if not osnovna or iznos <= 0:
        return None
    vrijednost = iznos * osnovna[1]
    if vrijednost > NAJVISE[osnovna[0]]:
        return None
    return round(vrijednost, 6), osnovna[0]


def iz_teksta(tekst: str) -> tuple[float, str] | None:
    """Traži količinu zapisanu u tekstu, npr. "Mlijeko 2,8% 1 l" ili "6x0,5 l"."""
    pakiranja = []
    if m := RE_VISE.search(tekst):
        pakiranja.append((m.group(1), m.group(2), m.group(3)))
    if m := RE_VISE_IZA.search(tekst):
        pakiranja.append((m.group(3), m.group(1), m.group(2)))
    for komada, iznos, jed in pakiranja:
        jedno = _u_osnovnu(float(iznos.replace(",", ".")), jed)
        if jedno and int(komada) > 0:
            return _u_osnovnu(int(komada) * jedno[0], jedno[1])
    for m in RE_JEDNO.finditer(tekst):
        rezultat = _u_osnovnu(float(m.group(1).replace(",", ".")), m.group(2))
        if rezultat:
            return rezultat
    return None


def mjera(kolicina: str, jedinica: str, naziv: str = "") -> tuple[float, str] | None:
    """
    Vraća (iznos, osnovna jedinica), npr. (0.5, "kg"), ili None ako se ne zna.
    Lanci upisuju količinu svakako ("500g", "0,5", "1 KOM"), pa probamo redom.
    """
    kolicina = (kolicina or "").strip()
    jedinica = (jedinica or "").strip().lower()

    rezultat = iz_teksta(kolicina)
    if not rezultat:
        broj = re.match(BROJ, kolicina)
        if broj and jedinica:
            rezultat = _u_osnovnu(float(broj.group(1).replace(",", ".")), jedinica)
        elif not kolicina and jedinica in ("kg", "l"):
            rezultat = (1.0, JEDINICE[jedinica][0])  # vaga se, cijena je po kg/l

    # Djelomičan komad ("2,5" kom) nije količina: pogrešno upisana jedinica, pa odlučuje naziv ("KRUMPIR 2,5 kg").
    if rezultat and rezultat[1] == "kom" and rezultat[0] != int(rezultat[0]):
        rezultat = None
    # "kom" često znači samo "jedno pakiranje" - u nazivu piše prava količina.
    if naziv and (not rezultat or rezultat[1] == "kom"):
        iz_naziva = iz_teksta(naziv)
        if iz_naziva and (not rezultat or rezultat[0] == 1):
            rezultat = iz_naziva
    if rezultat and rezultat[1] == "kom" and rezultat[0] != int(rezultat[0]):
        return None
    return rezultat


def polje_jedinicne(red: dict, mjera_proizvoda: tuple[float, str] | None) -> str | None:
    """
    Kojem polju retka pripada jedinična cijena koju je trgovac objavio (unit_price, po kg ili l): "price" (redovna) ili
    "special_price" (akcijska), uz količinu proizvoda i dopušteno samo zaokruživanje na 2 decimale.
    "" = nema se s čim usporediti (bez jedinične cijene ili bez količine u kg/l); None = ne odgovara ni jednom polju,
    tj. redak proturječi sam sebi. Jedinična cijena jednaka cijeni pakiranja koje nije 1 kg/l nije potvrda ni
    proturječje: lanac tada nije objavio stvarnu jediničnu cijenu (npr. Žabac, Branka, Stanić za gotovo sve
    artikle), pa je to "" (nije provjerljivo), kao redak bez jedinične cijene.
    """
    jedinicna = u_broj(red.get("unit_price") or "")
    if not jedinicna or not mjera_proizvoda or mjera_proizvoda[1] not in ("kg", "l"):
        return ""
    kolicina = mjera_proizvoda[0]
    for stupac in ("price", "special_price"):
        c = cijena_za_uvoz(red.get(stupac) or "")
        if c and abs(jedinicna - c / kolicina) <= 0.01 + 0.005 / kolicina + 1e-9:
            return stupac
    if any(c and abs(jedinicna - c) <= 0.005 for c in (cijena_za_uvoz(red.get(st) or "") for st in ("price", "special_price"))):
        return ""
    return None


def jedinicna_se_slaze(red: dict, mjera_proizvoda: tuple[float, str] | None) -> bool:
    return polje_jedinicne(red, mjera_proizvoda) is not None


def opis_mjere(iznos: float, jedinica: str) -> str:
    if jedinica == "kg" and iznos < 1:
        tekst, jedinica = f"{iznos * 1000:g}", "g"
    elif jedinica == "l" and iznos < 1:
        tekst, jedinica = f"{iznos * 1000:g}", "ml"
    else:
        tekst = f"{iznos:g}"
    return f"{tekst.replace('.', ',')} {jedinica}"


def broj_rijeci_marke(naziv: str, marka: str) -> int:
    """Koliko riječi na početku naziva je zapravo marka ("Dukat Mlijeko" -> 1)."""
    n, m = normaliziraj(naziv).split(), normaliziraj(marka or "").split()
    if m and len(n) > len(m) and n[: len(m)] == m:
        return len(m)
    return 0


def obradi(arhiva: Path, dopuna: dict | None = None, statistika: dict | None = None,
           primjeri: list | None = None) -> tuple[list, list]:
    """(lanci, proizvodi) - vidi obradi_sve."""
    r = obradi_sve(arhiva, dopuna, statistika, primjeri)
    return r["lanci"], r["proizvodi"]


def obradi_sve(arhiva: Path, dopuna: dict | None = None, statistika: dict | None = None,
               primjeri: list | None = None) -> dict:
    """
    Vraća {"lanci", "proizvodi", "poslovnice", "po_poslovnici"}.
    Proizvod = [naziv, količina (tekst), iznos, jedinica, riječi marke, [lanac, cijena, ...], [ponuda, ...]]
    gdje su iznos i jedinica količina svedena na kg/l/kom (0 i "" ako se ne zna), cijene po lancima idu od
    najjeftinije, a ponuda (isti redoslijed) = [poslovnica, poslovnica s proizvodom, najviša cijena, akcija]:
    cijena lanca je najniža valjana cijena jedne stvarne poslovnice (indeks u "poslovnice"), uz broj poslovnica
    lanca s valjanom cijenom, najvišu od njih (samo oznaka raspona za provjeru) i 1 ako je to akcijska cijena.
    poslovnice = [[lanac, store_id, adresa, grad], ...]; po_poslovnici = {poslovnica: [proizvod, cijena u centima, ...]}
    s valjanim cijenama te poslovnice (za zbroj cijelog popisa u jednoj stvarnoj poslovnici).
    statistika (lanac -> Counter) i primjeri (popis) se pune samo za reviziju cijena.
    """
    dopuna = dopuna or {}
    lanci: list[str] = []
    poslovnice: list[list] = []
    # Službene datoteke cjenika (URL, datum) za lance preuzete izravno; indeks je trag uz cijenu i poslovnicu.
    izvori: list[list] = []
    sluzbeni_lanci: set[int] = set()
    # ključ proizvoda -> {"naziv", "marka", "mjera", "provjerena", "cijene": {lanac: (cijena, ponuda)}, "redovi": {lanac: array}}
    svi: dict[str, dict] = {}

    with zipfile.ZipFile(arhiva) as zf:
        imena = set(zf.namelist())
        mape = sorted({n.split("/")[0] for n in imena if n.endswith("/prices.csv")})
        for lanac in mape:
            if lanac in PRESKOCI_LANCE:
                continue
            lanac_idx = len(lanci)
            lanci.append(LIJEPA_IMENA.get(lanac, lanac.capitalize()))
            st = statistika.setdefault(lanci[-1], Counter()) if statistika is not None else Counter()

            proizvodi = {p["product_id"]: p for p in citaj_csv(zf, f"{lanac}/products.csv")}
            podaci_trgovina = ({t.get("store_id"): t for t in citaj_csv(zf, f"{lanac}/stores.csv")}
                               if f"{lanac}/stores.csv" in imena else {})
            indeks_poslovnice: dict[str, int] = {}
            pomak_izvora = len(izvori)
            if f"{lanac}/izvori.json" in imena:
                izvori.extend(json.loads(zf.read(f"{lanac}/izvori.json")))
                sluzbeni_lanci.add(lanac_idx)

            def poslovnica(store_id: str, izvor: str = "") -> int:
                if store_id not in indeks_poslovnice:
                    t = podaci_trgovina.get(store_id) or {}
                    indeks_poslovnice[store_id] = len(poslovnice)
                    poslovnice.append([lanac_idx, store_id, (t.get("address") or "").strip(), (t.get("city") or "").strip(),
                                       pomak_izvora + int(izvor) if str(izvor).isdigit() else -1])
                return indeks_poslovnice[store_id]

            # Ponuda svake poslovnice: niža od redovne i akcijske cijene, uz oznaku koje je polje.
            po_proizvodu: dict[str, list] = {}
            for red in citaj_csv(zf, f"{lanac}/prices.csv"):
                redovna, akcijska = cijena_za_uvoz(red["price"]), cijena_za_uvoz(red.get("special_price", ""))
                # Službeni cjenik može navesti poseban oblik prodaje (npr. NTL "TNC") uz samu MPC: to je akcija.
                naziv_akcije = (red.get("akcija") or "").strip()
                oznaka = 1 if naziv_akcije and normaliziraj(naziv_akcije) not in ("ne", "0", "false") else 0
                if akcijska and (not redovna or akcijska < redovna):
                    po_proizvodu.setdefault(red["product_id"], []).append((akcijska, 1, red))
                elif redovna:
                    po_proizvodu.setdefault(red["product_id"], []).append((redovna, oznaka, red))
                else:
                    st["redak bez valjane cijene"] += 1

            uvezeno = 0
            for pid, redovi in po_proizvodu.items():
                p = proizvodi.get(pid)
                if not p or not (p.get("name") or "").strip():
                    continue
                barkod = (p.get("barcode") or "").strip()
                # Količina iz dopune, polja lanca ili naziva: vrijedi ona koju potvrđuje jedinična cijena koju je lanac
                # sam objavio za redovnu ili akcijsku cijenu (dopuna zna biti pogrešna, npr. pivo 2 l kao 0,4 kg).
                kandidati = []
                for m in (dopuna.get(barkod), mjera(p.get("quantity", ""), p.get("unit", ""), p["name"]), iz_teksta(p["name"])):
                    if m and m not in kandidati:
                        kandidati.append(m)
                mjera_lanca, valjani = None, []
                for m in kandidati:
                    v = [r for r in redovi if polje_jedinicne(r[2], m) is not None]
                    if len(v) > len(valjani):
                        mjera_lanca, valjani = m, v
                provjerena = bool(mjera_lanca) and any(polje_jedinicne(r[2], mjera_lanca) for r in redovi)
                # Nijedna količina ne slaže se s jediničnom cijenom lanca: cijene ostaju vidljive (stvarne objavljene
                # cijene poslovnica), ali bez količine, pa se ne rangiraju i ne miješaju s istim barkodom drugih lanaca.
                nepotvrdeno = bool(kandidati) and not valjani
                if not kandidati:
                    valjani = redovi
                elif nepotvrdeno:
                    valjani = redovi
                najbolja = min(valjani, key=lambda r: (r[0], r[2].get("store_id") or ""))
                cijena = najbolja[0]
                red_n = najbolja[2]
                ponuda = [poslovnica(red_n.get("store_id") or "", red_n.get("izvor", "")), len(valjani), max(r[0] for r in valjani),
                          najbolja[1]]
                if str(red_n.get("redak", "")).isdigit():
                    # Trag: redak u službenoj datoteci poslovnice i naziv akcije ako ga cjenik navodi.
                    naziv_akcije = (red_n.get("akcija") or "").strip()
                    ponuda += [int(red_n["redak"]), naziv_akcije if normaliziraj(naziv_akcije) not in ("", "da", "ne", "0", "1") else ""]
                st["proizvoda"] += 1
                st["redaka"] += len(redovi)
                if mjera_lanca and mjera_lanca[1] in ("kg", "l") and mjera_lanca[0] != 1:
                    st["jedinična jednaka cijeni pakiranja (nije provjerljivo)"] += sum(
                        1 for r in redovi if u_broj(r[2].get("unit_price") or "") and polje_jedinicne(r[2], mjera_lanca) == "")
                if not nepotvrdeno:
                    st["redak proturječan jediničnoj cijeni (ne rangira se, nije u zbroju poslovnice)"] += len(redovi) - len(valjani)
                if nepotvrdeno:
                    st["količina nepotvrđena jediničnom cijenom (prikaz bez poretka)"] += 1
                if mjera_lanca and mjera_lanca != kandidati[0]:
                    st["količina lanca umjesto dopune (potvrđena jediničnom cijenom)"] += 1
                if len({r[0] for r in valjani}) > 1:
                    st["poslovnice lanca imaju različite cijene (oznaka raspona)"] += 1
                if primjeri is not None:
                    primjeri.append({"lanac": lanci[-1], "product_id": pid, "naziv": p["name"].strip(),
                                     "kolicina": p.get("quantity"), "jedinica": p.get("unit"), "kandidati": kandidati,
                                     "mjera": None if nepotvrdeno else mjera_lanca, "poslovnica": len(redovi),
                                     "valjano": 0 if nepotvrdeno else len(valjani), "cijena": cijena,
                                     "prije": min(r[0] for r in redovi),
                                     "store_id": najbolja[2].get("store_id"), "polje": "special_price" if najbolja[1] else "price",
                                     "najvisa": ponuda[2],
                                     "raspon": sorted({(r[2].get("price"), r[2].get("special_price"), r[2].get("unit_price"))
                                                       for r in redovi}, key=lambda t: u_broj(t[0] or "") or 0)[:8]})
                uvezeno += 1
                # Isti barkod = isti proizvod, bez obzira na lanac.
                kljuc = barkod or f"{lanac}:{pid}"
                zapis = svi.get(kljuc)
                if nepotvrdeno:
                    kljuc = f"{kljuc}|nepotvrdeno|{lanac}"
                    zapis = svi.get(kljuc)
                elif zapis is not None and provjerena and zapis["provjerena"] and zapis["mjera"] != mjera_lanca:
                    kljuc = f"{kljuc}|{mjera_lanca}"
                    zapis = svi.get(kljuc)
                if zapis is None:
                    zapis = svi[kljuc] = {"cijene": {}, "redovi": {}, "mjera": None, "provjerena": False, "najniza": None}
                stara = zapis["cijene"].get(lanac_idx)
                if stara is None or cijena < stara[0]:
                    zapis["cijene"][lanac_idx] = (cijena, ponuda)
                # Valjane cijene po poslovnici (poslovnica, centi); isti proizvod lanca pod drugim product_id zadržava nižu.
                redovi_lanca = zapis["redovi"].setdefault(lanac_idx, array("i"))
                for r in valjani:
                    redak = r[2].get("redak", "")
                    redovi_lanca.extend((poslovnica(r[2].get("store_id") or "", r[2].get("izvor", "")), round(r[0] * 100),
                                         int(redak) if str(redak).isdigit() else 0))
                # Naziv uzimamo iz lanca s najnižom cijenom.
                if zapis["najniza"] is None or cijena < zapis["najniza"]:
                    zapis["najniza"] = cijena
                    zapis["naziv"] = p["name"].strip()
                    zapis["marka"] = (p.get("brand") or "").strip()
                if not nepotvrdeno and (zapis["mjera"] is None or (provjerena and not zapis["provjerena"])):
                    zapis["mjera"], zapis["provjerena"] = mjera_lanca, provjerena
            print(f"  {lanci[-1]}: {uvezeno} proizvoda, {len(indeks_poslovnice)} poslovnica")

    zapisi = sorted(svi.values(), key=lambda z: min(c for c, _ in z["cijene"].values()))
    proizvodi, po_poslovnici, marke, indeks_marke = [], {}, [], {}
    for i, z in enumerate(zapisi):
        # Stvarna marka iz cjenika (indeks u "marke", -1 ako je cjenik ne navodi) za filtar "Samo ova marka".
        marka = re.sub(r"\s+", " ", z["marka"] or "").strip()
        if marka and marka.casefold() not in indeks_marke:
            indeks_marke[marka.casefold()] = len(marke)
            marke.append(marka)
        cijene = sorted(z["cijene"].items(), key=lambda lc: lc[1][0])
        iznos, jedinica = z["mjera"] or (0, "")
        proizvodi.append([
            z["naziv"],
            opis_mjere(iznos, jedinica) if jedinica else "",
            iznos,
            jedinica,
            broj_rijeci_marke(z["naziv"], z["marka"]),
            [x for lanac, (c, _) in cijene for x in (lanac, round(c, 2))],
            [[pon[0], pon[1], round(pon[2], 2), *pon[3:]] for _, (_, pon) in cijene],
            indeks_marke[marka.casefold()] if marka else -1,
        ])
        # Proizvodi idu redom (i raste), pa je isti proizvod u istoj poslovnici uvijek zadnji upisani.
        # Trojke (proizvod, centi, redak u službenoj datoteci ili 0).
        for redovi_lanca in z["redovi"].values():
            for k in range(0, len(redovi_lanca), 3):
                cj = po_poslovnici.setdefault(redovi_lanca[k], array("i"))
                if cj and cj[-3] == i:
                    if redovi_lanca[k + 1] < cj[-2]:
                        cj[-2], cj[-1] = redovi_lanca[k + 1], redovi_lanca[k + 2]
                else:
                    cj.extend((i, redovi_lanca[k + 1], redovi_lanca[k + 2]))
        z["redovi"] = None
    return {"lanci": lanci, "proizvodi": proizvodi, "poslovnice": poslovnice, "po_poslovnici": po_poslovnici, "marke": marke,
            "izvori": izvori, "sluzbeni_lanci": sluzbeni_lanci}


def zapisi_poslovnice(mapa: Path, rezultat: dict, datum: str) -> int:
    """Jedna datoteka po stvarnoj poslovnici: [proizvod (razlika od prethodnog), cijena u centima, ...]."""
    mapa.mkdir(parents=True, exist_ok=True)
    for stara in mapa.glob("*.json"):
        stara.unlink()
    for s, cj in rezultat["po_poslovnici"].items():
        kompaktno, redci, prije = [], [], 0
        for k in range(0, len(cj), 3):
            kompaktno.extend((cj[k] - prije, cj[k + 1]))
            redci.append(cj[k + 2])
            prije = cj[k]
        zapis = {"datum": datum, "proizvoda": len(rezultat["proizvodi"]), "c": kompaktno}
        izvor = rezultat["poslovnice"][s][4] if len(rezultat["poslovnice"][s]) > 4 else -1
        if izvor >= 0 and any(redci):
            # Službena datoteka poslovnice i redak svake cijene u njoj (isti redoslijed kao "c").
            zapis["izvor"], zapis["r"] = rezultat["izvori"][izvor], redci
        (mapa / f"{s}.json").write_text(json.dumps(zapis, separators=(",", ":")), encoding="utf-8")
    return len(rezultat["po_poslovnici"])


def sastavi_arhivu(arhiva: Path, d, odrediste: Path, rok_sekundi: float = 2400, lanci_sluzbeno=None) -> dict:
    """
    Arhiva u obliku cijene.dev u kojoj je svaki lanac čiji se današnji službeni cjenici mogu preuzeti i pročitati
    zamijenjen tim službenim podacima (s tragom URL/redak/datum u prices.csv i izvori.json). Ostali lanci ostaju iz
    arhive cijene.dev (neprovjereno prema službenom izvoru). Vraća izvještaj po lancu.
    """
    import time
    import sluzbeni_cjenici as sl
    izvjestaj, pocetak = {}, time.time()
    with zipfile.ZipFile(arhiva) as ulaz, zipfile.ZipFile(odrediste, "w", zipfile.ZIP_DEFLATED) as izlaz:
        mape = sorted({n.split("/")[0] for n in ulaz.namelist() if n.endswith("/prices.csv")})
        for lanac in sorted(set(mape) | set(sl.LANCI)):
            if lanac in PRESKOCI_LANCE:
                continue
            zapis = {"izvor": "cijene.dev", "razlog": ""}
            if lanci_sluzbeno is not None and lanac not in lanci_sluzbeno:
                zapis["razlog"] = "nije u ovom pokretanju"
            elif lanac not in sl.LANCI:
                zapis["razlog"] = "službeni čitač za lanac još ne postoji"
            elif time.time() - pocetak > rok_sekundi:
                zapis["razlog"] = "vremensko ograničenje pokretanja"
            else:
                t = time.time()
                rez = sl.preuzmi_lanac(lanac, d)
                zapis.update({"datoteka": len(rez["datoteke"]), "neuspjelih_datoteka": sum(1 for x in rez["datoteke"] if x["greska"]),
                              "primjer_greske": next((x["greska"] for x in rez["datoteke"] if x["greska"]), ""),
                              "sekundi": round(time.time() - t)})
                if rez["uspjeh"]:
                    trgovine, proizvodi_csv, cijene_csv, izvori = sl.u_arhivu_lanca(rez, d)
                    izlaz.writestr(f"{lanac}/stores.csv", trgovine)
                    izlaz.writestr(f"{lanac}/products.csv", proizvodi_csv)
                    izlaz.writestr(f"{lanac}/prices.csv", cijene_csv)
                    izlaz.writestr(f"{lanac}/izvori.json", json.dumps(izvori, ensure_ascii=False))
                    zapis.update({"izvor": "službeni cjenici", "poslovnica": len(rez["koristene"]),
                                  "redaka": sum(len(x["zapisi"]) for x in rez["koristene"]),
                                  "nepoznati_stupci": sorted({n for x in rez["koristene"] for n in x["nepoznati"]})[:15]})
                    izvjestaj[lanac] = zapis
                    print(f"  službeno {lanac}: {zapis['poslovnica']} poslovnica, {zapis['redaka']} redaka ({zapis['sekundi']} s)", flush=True)
                    continue
                zapis["razlog"] = rez["razlog"]
            if lanac in mape:
                for ime in ("stores.csv", "products.csv", "prices.csv"):
                    if f"{lanac}/{ime}" in ulaz.namelist():
                        izlaz.writestr(f"{lanac}/{ime}", ulaz.read(f"{lanac}/{ime}"))
            else:
                zapis["izvor"] = "nema podataka"
            izvjestaj[lanac] = zapis
            print(f"  {zapis['izvor']} {lanac}: {zapis['razlog']}", flush=True)
    return izvjestaj


def pokrivenost(rezultat: dict, statistika: dict, datum: str, izvjestaj: dict | None = None) -> dict:
    """
    Pokrivenost po lancu. Ponude lanca preuzetog izravno iz današnjih službenih cjenika imaju trag (URL datoteke,
    redak, datum) i broje se kao provjerene prema službenom izvoru; ponude lanaca iz arhive cijene.dev (sekundarni
    izvor bez URL-a, datoteke i retka službenog cjenika) nisu provjerene. Za lanac bez službenih podataka naveden je razlog.
    """
    ponuda = Counter(l for p in rezultat["proizvodi"] for l in p[5][0::2])
    poslovnica = Counter(p[0] for p in rezultat["poslovnice"])
    sluzbeni = rezultat.get("sluzbeni_lanci", set())
    obrnuto = {v: k for k, v in LIJEPA_IMENA.items()}
    lanci = {}
    for idx, ime in enumerate(rezultat["lanci"]):
        st = statistika.get(ime, Counter())
        provjereno = ponuda[idx] if idx in sluzbeni else 0
        lanci[ime] = {"ponuda": ponuda[idx], "poslovnica": poslovnica[idx], "redaka": st["redaka"],
                      "izvor": "službeni cjenici" if idx in sluzbeni else "cijene.dev",
                      **({k: v for k, v in (izvjestaj or {}).get(obrnuto.get(ime, ime), {}).items() if k != "izvor"}),
                      "provjereno_prema_sluzbenom_izvoru": provjereno, "neprovjereno": ponuda[idx] - provjereno,
                      "redak_proturjecan_jedinicnoj": st["redak proturječan jediničnoj cijeni (ne rangira se, nije u zbroju poslovnice)"],
                      "kolicina_nepotvrdena": st["količina nepotvrđena jediničnom cijenom (prikaz bez poretka)"],
                      "redak_bez_valjane_cijene": st["redak bez valjane cijene"]}
    provjereno = sum(x["provjereno_prema_sluzbenom_izvoru"] for x in lanci.values())
    return {"izvor": (f"službeni cjenici lanaca {datum} (URL/redak uz svaku cijenu) za {len(sluzbeni)} lanaca; ostali iz "
                      "arhive cijene.dev (sekundarni izvor, bez traga do službene datoteke)") if sluzbeni else
            f"arhiva cijene.dev {datum} (sekundarni izvor; bez traga do službene datoteke)", "datum": datum,
            "ukupno_ponuda": sum(ponuda.values()), "provjereno_prema_sluzbenom_izvoru": provjereno, "lanci": lanci,
            "bez_podataka": {k: v for k, v in (izvjestaj or {}).items() if v.get("izvor") == "nema podataka"}}


def main():
    import os
    from zoneinfo import ZoneInfo
    dopuna = preuzmi_dopunu()
    statistika: dict = {}
    izvjestaj = None
    if len(sys.argv) > 1:
        arhiva = Path(sys.argv[1])
        datum = arhiva.stem
        rezultat = obradi_sve(arhiva, dopuna, statistika)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            arhiva = Path(tmp) / "cijene.zip"
            datum = preuzmi_najnoviju_arhivu(arhiva)
            # Službeni cjenici imaju prednost; SLUZBENI=0 isključuje, SLUZBENI_LANCI=konzum,lidl ograničava.
            if os.environ.get("SLUZBENI", "1") != "0":
                # Jedan datum za cijelo pokretanje (SLUZBENI_DATUM), da prijelaz ponoći ne promijeni traženi dan.
                danas = (datetime.fromisoformat(os.environ["SLUZBENI_DATUM"]).date() if os.environ.get("SLUZBENI_DATUM")
                         else datetime.now(ZoneInfo("Europe/Zagreb")).date())
                sastavljena = Path(tmp) / "sastavljeno.zip"
                odabrani = [x for x in os.environ.get("SLUZBENI_LANCI", "").split(",") if x] or None
                izvjestaj = sastavi_arhivu(arhiva, danas, sastavljena, float(os.environ.get("SLUZBENI_ROK", "2400")), odabrani)
                if any(v["izvor"] == "službeni cjenici" for v in izvjestaj.values()):
                    arhiva, datum = sastavljena, danas.isoformat()
            rezultat = obradi_sve(arhiva, dopuna, statistika)
    lanci, proizvodi = rezultat["lanci"], rezultat["proizvodi"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    broj_datoteka = zapisi_poslovnice(OUTPUT.parent / "poslovnice", rezultat, datum)
    pokriveno = pokrivenost(rezultat, statistika, datum, izvjestaj)
    podaci = {
        "verzija": 2,
        "datum": datum,
        "azurirano": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "izvor": pokriveno["izvor"],
        "provjereno_prema_sluzbenom_izvoru": pokriveno["provjereno_prema_sluzbenom_izvoru"],
        "lanci": lanci,
        "izvori": rezultat["izvori"],
        "poslovnice": rezultat["poslovnice"],
        "marke": rezultat["marke"],
        "proizvodi": proizvodi,
    }
    OUTPUT.write_text(json.dumps(podaci, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUTPUT.parent / "pokrivenost.json").write_text(json.dumps(pokriveno, ensure_ascii=False, indent=1), encoding="utf-8")
    s_mjerom = sum(1 for p in proizvodi if p[3])
    print(
        f"Gotovo: {len(proizvodi)} jedinstvenih proizvoda iz {len(lanci)} lanaca "
        f"({s_mjerom} s poznatom količinom), {broj_datoteka} poslovnica -> {OUTPUT}"
    )
    print("Pokrivenost: " + json.dumps({k: v for k, v in pokriveno.items() if k != "lanci"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
