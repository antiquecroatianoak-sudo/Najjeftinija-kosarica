"""
Dnevno preuzimanje cijena iz svih hrvatskih trgovačkih lanaca.

Izvor: javni cjenici koje lanci moraju objavljivati (NN 75/2025), koje
projekt cijene.dev svaki dan skuplja u jednu ZIP arhivu.

Skripta:
  1. preuzme najnoviju arhivu,
  2. za svaki proizvod nađe najnižu cijenu u svakom lancu,
  3. spoji iste proizvode iz različitih lanaca (po barkodu) - bez duplikata,
  4. zapiše mali JSON koji koristi web aplikacija.

Pokretanje:  python scripts/azuriraj_cijene.py [put/do/arhive.zip]
"""

import csv
import io
import json
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

LIST_URL = "https://api.cijene.dev/v0/list"
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


def preuzmi_najnoviju_arhivu(odrediste: Path) -> str:
    with urllib.request.urlopen(LIST_URL, timeout=60) as r:
        arhive = json.load(r)["archives"]
    najnovija = max(arhive, key=lambda a: a["date"])
    print(f"Preuzimam arhivu za {najnovija['date']} ({najnovija['size'] // 1_000_000} MB)")
    urllib.request.urlretrieve(najnovija["url"], odrediste)
    return najnovija["date"]


def u_broj(vrijednost: str) -> float | None:
    try:
        broj = float(vrijednost.replace(",", "."))
    except (AttributeError, ValueError):
        return None
    return broj if broj > 0 else None


def citaj_csv(zf: zipfile.ZipFile, ime: str):
    with zf.open(ime) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))


def kolicina(proizvod: dict) -> str:
    q = (proizvod.get("quantity") or "").strip()
    u = (proizvod.get("unit") or "").strip().lower()
    if not q:
        return u
    try:
        q = f"{float(q.replace(',', '.')):g}".replace(".", ",")
    except ValueError:
        pass
    return f"{q} {u}".strip()


def obradi(arhiva: Path) -> tuple[list, list]:
    """Vraća (lanci, proizvodi). Proizvod = [naziv, količina, indeks_lanca, cijena]."""
    lanci: list[str] = []
    # barkod -> {"naziv", "kolicina", "cijena", "lanac"}
    najbolji: dict[str, dict] = {}

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
                cijene = [c for c in (u_broj(red["price"]), u_broj(red.get("special_price", ""))) if c]
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
                kljuc = (p.get("barcode") or "").strip() or f"{lanac}:{pid}"
                postojeci = najbolji.get(kljuc)
                if postojeci is None or cijena < postojeci["cijena"]:
                    najbolji[kljuc] = {
                        "naziv": p["name"].strip(),
                        "kolicina": kolicina(p),
                        "cijena": cijena,
                        "lanac": lanac_idx,
                    }
            print(f"  {lanci[-1]}: {len(min_cijena)} proizvoda")

    proizvodi = sorted(
        ([v["naziv"], v["kolicina"], v["lanac"], round(v["cijena"], 2)] for v in najbolji.values()),
        key=lambda x: x[3],
    )
    return lanci, proizvodi


def main():
    if len(sys.argv) > 1:
        arhiva = Path(sys.argv[1])
        datum = arhiva.stem
        lanci, proizvodi = obradi(arhiva)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            arhiva = Path(tmp) / "cijene.zip"
            datum = preuzmi_najnoviju_arhivu(arhiva)
            lanci, proizvodi = obradi(arhiva)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    podaci = {
        "datum": datum,
        "azurirano": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "lanci": lanci,
        "proizvodi": proizvodi,
    }
    OUTPUT.write_text(json.dumps(podaci, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Gotovo: {len(proizvodi)} jedinstvenih proizvoda iz {len(lanci)} lanaca -> {OUTPUT}")


if __name__ == "__main__":
    main()
