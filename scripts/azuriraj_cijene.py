"""
Dnevno preuzimanje cijena iz svih hrvatskih trgovačkih lanaca.

Izvor: javni cjenici koje lanci moraju objavljivati (NN 75/2025), koje
projekt cijene.dev svaki dan skuplja u jednu ZIP arhivu.

Skripta:
  1. preuzme najnoviju arhivu,
  2. za svaki proizvod nađe najnižu cijenu u svakom lancu,
  3. spoji iste proizvode iz različitih lanaca (po barkodu) - bez duplikata,
  4. prepozna količinu (g, kg, ml, l, kom) da se može računati cijena po kg/l,
  5. zapiše mali JSON koji koristi web aplikacija.

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
    "mg": ("kg", 0.000001), "g": ("kg", 0.001), "gr": ("kg", 0.001), "dag": ("kg", 0.01),
    "kg": ("kg", 1),
    "ml": ("l", 0.001), "cl": ("l", 0.01), "dl": ("l", 0.1),
    "l": ("l", 1), "lit": ("l", 1), "litra": ("l", 1), "ltr": ("l", 1),
    "kom": ("kom", 1), "komad": ("kom", 1), "kos": ("kom", 1), "par": ("kom", 1),
    "pak": ("kom", 1), "kut": ("kom", 1),
}
# Razumne granice da pogrešno upisana količina ne pokvari cijenu po kg/l.
NAJVISE = {"kg": 50, "l": 50, "kom": 500}

BROJ = r"(\d+(?:[.,]\d+)?)"
JED = r"(mg|g|gr|dag|kg|ml|cl|dl|l|lit|litra|ltr|kom|komad|kos|par|pak|kut)\b\.?"
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

    # "kom" često znači samo "jedno pakiranje" - u nazivu piše prava količina.
    if naziv and (not rezultat or rezultat[1] == "kom"):
        iz_naziva = iz_teksta(naziv)
        if iz_naziva and (not rezultat or rezultat[0] == 1):
            rezultat = iz_naziva
    return rezultat


def uskladi_s_nazivom(rezultat: tuple[float, str] | None, naziv: str) -> tuple[float, str] | None:
    """
    Polje količine ili dopuna ponekad imaju pogrešan decimalni red ("KRUH 310 g" zapisan kao 31 kg).
    Ako naziv izričito navodi količinu iste jedinice, a razlika je točno 10, 100 ili 1000 puta,
    vrijedi naziv. Ostale razlike (npr. pakiranje 6 boca prema "0,5 l" u nazivu) ostaju kako jesu.
    """
    iz_naziva = iz_teksta(naziv or "")
    if not rezultat or not iz_naziva or rezultat[1] != iz_naziva[1] or rezultat[1] == "kom":
        return rezultat
    omjer = max(rezultat[0], iz_naziva[0]) / min(rezultat[0], iz_naziva[0])
    if any(abs(omjer - f) < 1e-6 * f for f in (10, 100, 1000)):
        return iz_naziva
    return rezultat


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


def obradi(arhiva: Path, dopuna: dict | None = None) -> tuple[list, list]:
    """
    Vraća (lanci, proizvodi).
    Proizvod = [naziv, količina (tekst), iznos, jedinica, riječi marke, [lanac, cijena, lanac, cijena, ...]]
    gdje su iznos i jedinica količina svedena na kg/l/kom (0 i "" ako se ne zna),
    a cijene po lancima idu od najjeftinije.
    """
    dopuna = dopuna or {}
    lanci: list[str] = []
    # barkod -> {"naziv", "marka", "kolicina", "jedinica", "mjera", "cijene": {lanac: cijena}}
    svi: dict[str, dict] = {}

    with zipfile.ZipFile(arhiva) as zf:
        mape = sorted({n.split("/")[0] for n in zf.namelist() if n.endswith("/prices.csv")})
        for lanac in mape:
            if lanac in PRESKOCI_LANCE:
                continue
            lanac_idx = len(lanci)
            lanci.append(LIJEPA_IMENA.get(lanac, lanac.capitalize()))

            proizvodi = {p["product_id"]: p for p in citaj_csv(zf, f"{lanac}/products.csv")}

            # Najniža cijena svakog proizvoda u bilo kojoj poslovnici lanca
            # (uzimamo i akcijsku cijenu ako postoji).
            min_cijena: dict[str, float] = {}
            for red in citaj_csv(zf, f"{lanac}/prices.csv"):
                cijene = [c for c in (cijena_za_uvoz(red["price"]), cijena_za_uvoz(red.get("special_price", ""))) if c]
                if not cijene:
                    continue
                c = min(cijene)
                pid = red["product_id"]
                if pid not in min_cijena or c < min_cijena[pid]:
                    min_cijena[pid] = c

            for pid, cijena in min_cijena.items():
                p = proizvodi.get(pid)
                if not p or not (p.get("name") or "").strip():
                    continue
                # Isti barkod = isti proizvod, bez obzira na lanac.
                barkod = (p.get("barcode") or "").strip()
                kljuc = barkod or f"{lanac}:{pid}"
                zapis = svi.get(kljuc)
                if zapis is None:
                    zapis = svi[kljuc] = {"cijene": {}, "mjera": None, "najniza": None}
                stara = zapis["cijene"].get(lanac_idx)
                if stara is None or cijena < stara:
                    zapis["cijene"][lanac_idx] = cijena
                # Naziv uzimamo iz lanca s najnižom cijenom.
                if zapis["najniza"] is None or cijena < zapis["najniza"]:
                    zapis["najniza"] = cijena
                    zapis["naziv"] = p["name"].strip()
                    zapis["marka"] = (p.get("brand") or "").strip()
                if zapis["mjera"] is None:
                    zapis["mjera"] = uskladi_s_nazivom(dopuna.get(barkod) or mjera(
                        p.get("quantity", ""), p.get("unit", ""), p["name"]
                    ), p["name"])
            print(f"  {lanci[-1]}: {len(min_cijena)} proizvoda")

    proizvodi = []
    for z in svi.values():
        cijene = sorted(z["cijene"].items(), key=lambda lc: lc[1])
        iznos, jedinica = z["mjera"] or (0, "")
        proizvodi.append([
            z["naziv"],
            opis_mjere(iznos, jedinica) if jedinica else "",
            iznos,
            jedinica,
            broj_rijeci_marke(z["naziv"], z["marka"]),
            [x for lanac, c in cijene for x in (lanac, round(c, 2))],
        ])
    proizvodi.sort(key=lambda p: p[5][1])
    return lanci, proizvodi


def main():
    dopuna = preuzmi_dopunu()
    if len(sys.argv) > 1:
        arhiva = Path(sys.argv[1])
        datum = arhiva.stem
        lanci, proizvodi = obradi(arhiva, dopuna)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            arhiva = Path(tmp) / "cijene.zip"
            datum = preuzmi_najnoviju_arhivu(arhiva)
            lanci, proizvodi = obradi(arhiva, dopuna)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    podaci = {
        "verzija": 2,
        "datum": datum,
        "azurirano": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "lanci": lanci,
        "proizvodi": proizvodi,
    }
    OUTPUT.write_text(json.dumps(podaci, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    s_mjerom = sum(1 for p in proizvodi if p[3])
    print(
        f"Gotovo: {len(proizvodi)} jedinstvenih proizvoda iz {len(lanci)} lanaca "
        f"({s_mjerom} s poznatom količinom) -> {OUTPUT}"
    )


if __name__ == "__main__":
    main()
