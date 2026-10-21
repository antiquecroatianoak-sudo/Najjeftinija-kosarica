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


def sazetak(statistika: dict, primjeri: list, rijec: str) -> dict:
    trazeno = a.normaliziraj(rijec)
    po_lancu = {}
    for lanac, st in statistika.items():
        st = Counter(st)
        for p in primjeri:
            if p["lanac"] != lanac:
                continue
            k = (p["kolicina"] or "").replace(",", ".")
            try:
                djelomican = (p["jedinica"] or "").strip().lower() in ("kom", "komad") and float(k) != int(float(k))
            except ValueError:
                djelomican = False
            st["djelomičan komad u izvoru (odlučuje naziv)"] += djelomican
            st["nepoznata količina (bez cijene po jedinici)"] += p["mjera"] is None
        po_lancu[lanac] = dict(st)
    odstupanja = sorted((p for p in primjeri if p["poslije"] and p["prije"] < p["poslije"]),
                        key=lambda p: p["prije"] / p["poslije"])
    return {
        "po_lancu": po_lancu,
        "ukupno": dict(sum((Counter(s) for s in po_lancu.values()), Counter())),
        "najveca_odstupanja_najnize_poslovnice": odstupanja[:40],
        "proturjecne_jedinicne": [p for p in primjeri if p["proturjecni"]][:40],
        "rijec": rijec,
        "prije_poslije": sorted(
            ({k: p[k] for k in ("lanac", "naziv", "kolicina", "jedinica", "mjera", "poslovnica", "potvrdeno", "prije", "poslije")}
             for p in primjeri if trazeno in a.normaliziraj(p["naziv"])),
            key=lambda p: (p["prije"] / p["mjera"][0]) if p["mjera"] else 1e9)[:60],
    }


def main():
    rijec = sys.argv[1] if len(sys.argv) > 1 else "krumpir"
    dopuna = a.preuzmi_dopunu()
    statistika, primjeri = {}, []
    with tempfile.TemporaryDirectory() as tmp:
        arhiva = Path(tmp) / "cijene.zip"
        datum = a.preuzmi_najnoviju_arhivu(arhiva)
        a.obradi(arhiva, dopuna, statistika=statistika, primjeri=primjeri)
    rezultat = {"arhiva": datum, **sazetak(statistika, primjeri, rijec)}
    IZLAZ.parent.mkdir(parents=True, exist_ok=True)
    IZLAZ.write_text(json.dumps(rezultat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Arhiva {datum}")
    print("Ukupno: " + json.dumps(rezultat["ukupno"], ensure_ascii=False))
    for lanac, st in rezultat["po_lancu"].items():
        print(f"{lanac}: " + json.dumps(st, ensure_ascii=False))
    print(f"Prije/poslije za '{rijec}' (od najniže cijene po jedinici prije):")
    for p in rezultat["prije_poslije"][:25]:
        print("  " + json.dumps(p, ensure_ascii=False))
    print("Najveća odstupanja najniže poslovnice od cijene lanca:")
    for p in rezultat["najveca_odstupanja_najnize_poslovnice"][:20]:
        print("  " + json.dumps({k: p[k] for k in ("lanac", "naziv", "poslovnica", "prije", "poslije")}, ensure_ascii=False))
    print("Primjeri proturječnih jediničnih cijena:")
    for p in rezultat["proturjecne_jedinicne"][:20]:
        print("  " + json.dumps({k: p[k] for k in ("lanac", "naziv", "mjera", "proturjecni")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
