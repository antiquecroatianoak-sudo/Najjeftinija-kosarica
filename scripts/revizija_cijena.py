"""
Revizija cijena na stvarnom cjeniku (samo čitanje, bez objave): python scripts/revizija_cijena.py [krumpir]

Za svaki lanac broji retke i proizvode koje uvoz ne rangira (bez valjane cijene, jedinična cijena trgovca proturječi
cijeni i količini, nema potvrđene cijene), proizvode čija je najniža poslovnica ispod cijene lanca (prije: cijena lanca
bila je ta najniža poslovnica), djelomične komade i nepoznate količine. Zapisuje site/data/revizija-cijena.json s
primjerima i usporedbom prije/poslije za traženu riječ.
"""
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import azuriraj_cijene as a  # noqa: E402

IZLAZ = Path(__file__).resolve().parent.parent / "site" / "data" / "revizija-cijena.json"


def djelomican(p: dict) -> bool:
    k = (p["kolicina"] or "").replace(",", ".")
    try:
        return (p["jedinica"] or "").strip().lower() in ("kom", "komad") and float(k) != int(float(k))
    except ValueError:
        return False


def sazetak(statistika: dict, primjeri: list, rijec: str) -> dict:
    trazeno = a.normaliziraj(rijec)
    po_lancu, uzorci = {}, {}
    for lanac, st in statistika.items():
        st = Counter(st)
        u = uzorci[lanac] = {"djelomičan komad": [], "nepotvrđena količina": [], "količina lanca umjesto dopune": []}
        for p in primjeri:
            if p["lanac"] != lanac:
                continue
            st["djelomičan komad u izvoru (odlučuje naziv)"] += djelomican(p)
            st["nepoznata količina (bez cijene po jedinici)"] += p["mjera"] is None
            for vrsta, uvjet in (("djelomičan komad", djelomican(p)), ("nepotvrđena količina", p["kandidati"] and not p["valjano"]),
                                 ("količina lanca umjesto dopune", p["kandidati"] and p["mjera"] and p["mjera"] != p["kandidati"][0])):
                if uvjet and len(u[vrsta]) < 3:
                    u[vrsta].append({k: p[k] for k in ("naziv", "kolicina", "jedinica", "kandidati", "mjera", "raspon")})
        po_lancu[lanac] = dict(st)
    return {
        "po_lancu": po_lancu,
        "ukupno": dict(sum((Counter(s) for s in po_lancu.values()), Counter())),
        # Oznaka za provjeru (nije dokaz greške): najveći raspon valjanih cijena među poslovnicama istog lanca.
        "najveci_rasponi_za_provjeru": sorted(primjeri, key=lambda p: p["cijena"] / p["najvisa"])[:40],
        "uzorci_po_lancu": uzorci,
        "rijec": rijec,
        "prije_poslije": sorted(
            ({k: p[k] for k in ("lanac", "naziv", "kolicina", "jedinica", "mjera", "poslovnica", "valjano", "prije", "cijena",
                                "store_id", "polje", "najvisa")}
             for p in primjeri if trazeno in a.normaliziraj(p["naziv"])),
            key=lambda p: (p["cijena"] / p["mjera"][0]) if p["mjera"] else 1e9)[:60],
    }


def main():
    rijec = sys.argv[1] if len(sys.argv) > 1 else "krumpir"
    dopuna = a.preuzmi_dopunu()
    statistika, primjeri = {}, []
    with tempfile.TemporaryDirectory() as tmp:
        arhiva = Path(tmp) / "cijene.zip"
        datum = a.preuzmi_najnoviju_arhivu(arhiva)
        a.obradi_sve(arhiva, dopuna, statistika=statistika, primjeri=primjeri)
    rezultat = {"arhiva": datum, **sazetak(statistika, primjeri, rijec)}
    IZLAZ.parent.mkdir(parents=True, exist_ok=True)
    IZLAZ.write_text(json.dumps(rezultat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Arhiva {datum}")
    print(f"Prije/poslije za '{rijec}' (od najniže cijene po jedinici prije):")
    for p in rezultat["prije_poslije"][:25]:
        print("  " + json.dumps(p, ensure_ascii=False))
    print("Najveći rasponi među poslovnicama lanca, za provjeru (sirovi retci: price, special_price, unit_price):")
    for p in rezultat["najveci_rasponi_za_provjeru"][:25]:
        print("  " + json.dumps({k: p[k] for k in ("lanac", "naziv", "poslovnica", "valjano", "cijena", "store_id", "najvisa", "raspon")}, ensure_ascii=False))
    print("Uzorci po lancu:")
    for lanac, u in rezultat["uzorci_po_lancu"].items():
        for vrsta, lista in u.items():
            for p in lista[:2]:
                print(f"  {lanac} · {vrsta}: " + json.dumps(p, ensure_ascii=False))
    print("Ukupno: " + json.dumps(rezultat["ukupno"], ensure_ascii=False))
    for lanac, st in rezultat["po_lancu"].items():
        print(f"{lanac}: " + json.dumps(st, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
