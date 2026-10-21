"""
Dijagnoza cijena jednog proizvoda na stvarnom cjeniku (samo čitanje): python scripts/dijagnoza_proizvoda.py krumpir

Za svaki lanac iz najnovije cijene.dev arhive ispisuje sve proizvode čiji naziv sadrži traženu riječ, sve njihove retke
cijena po poslovnici (sirovi stupci), te što uvoz od toga napravi: odabranu cijenu (najniža od price i special_price u
bilo kojoj poslovnici), prepoznatu količinu i cijenu po jedinici. Ništa ne mijenja i ne objavljuje.
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import azuriraj_cijene as a  # noqa: E402

IZLAZ = Path(__file__).resolve().parent.parent / "site" / "data" / "dijagnoza.json"


def dijagnoza(arhiva: Path, rijec: str, dopuna: dict) -> list[dict]:
    trazeno = a.normaliziraj(rijec)
    rezultat = []
    with zipfile.ZipFile(arhiva) as zf:
        imena = zf.namelist()
        for lanac in sorted({n.split("/")[0] for n in imena if n.endswith("/prices.csv")}):
            proizvodi = {p["product_id"]: p for p in a.citaj_csv(zf, f"{lanac}/products.csv")
                         if trazeno in a.normaliziraj(p.get("name") or "")}
            if not proizvodi:
                continue
            trgovine = {}
            if f"{lanac}/stores.csv" in imena:
                trgovine = {s.get("store_id"): s for s in a.citaj_csv(zf, f"{lanac}/stores.csv")}
            retci = {}
            for red in a.citaj_csv(zf, f"{lanac}/prices.csv"):
                if red["product_id"] in proizvodi:
                    retci.setdefault(red["product_id"], []).append(red)
            for pid, p in proizvodi.items():
                redovi = retci.get(pid, [])
                kandidati = []
                for red in redovi:
                    for stupac in ("price", "special_price"):
                        c = a.cijena_za_uvoz(red.get(stupac, ""))
                        if c:
                            kandidati.append((c, stupac, red))
                odabrano = min(kandidati, key=lambda x: x[0]) if kandidati else None
                barkod = (p.get("barcode") or "").strip()
                mjera = dopuna.get(barkod) or a.mjera(p.get("quantity", ""), p.get("unit", ""), p.get("name", ""))
                zapis = {
                    "lanac": lanac, "lanac_preskocen": lanac in a.PRESKOCI_LANCE, "product_id": pid,
                    "proizvod": {k: p.get(k) for k in p},
                    "mjera_uvoza": mjera, "mjera_iz_dopune": barkod in dopuna,
                    "redaka_cijena": len(redovi),
                    "odabrana_cijena": odabrano[0] if odabrano else None,
                    "odabrani_stupac": odabrano[1] if odabrano else None,
                    "odabrani_redak": odabrano[2] if odabrano else None,
                    "trgovina_odabranog": trgovine.get(odabrano[2].get("store_id")) if odabrano else None,
                    "po_jedinici": round(odabrano[0] / mjera[0], 4) if odabrano and mjera and mjera[0] else None,
                    "sve_cijene": sorted({(r.get("price"), r.get("special_price"), r.get("unit_price")) for r in redovi},
                                         key=lambda t: a.u_broj(t[0] or "") or 0)[:12],
                    "stupci_cijena": sorted(redovi[0].keys()) if redovi else [],
                }
                rezultat.append(zapis)
    return sorted(rezultat, key=lambda z: (z["po_jedinici"] is None, z["po_jedinici"] or 0))


def main():
    rijec = sys.argv[1] if len(sys.argv) > 1 else "krumpir"
    dopuna = a.preuzmi_dopunu()
    with tempfile.TemporaryDirectory() as tmp:
        arhiva = Path(tmp) / "cijene.zip"
        datum = a.preuzmi_najnoviju_arhivu(arhiva)
        rezultat = dijagnoza(arhiva, rijec, dopuna)
    IZLAZ.parent.mkdir(parents=True, exist_ok=True)
    IZLAZ.write_text(json.dumps({"arhiva": datum, "rijec": rijec, "proizvodi": rezultat}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"Arhiva {datum}: {len(rezultat)} proizvoda s riječi '{rijec}'")
    for z in rezultat[:60]:
        p = z["proizvod"]
        print(json.dumps({"lanac": z["lanac"], "naziv": p.get("name"), "kolicina": p.get("quantity"), "jedinica": p.get("unit"),
                          "barkod": p.get("barcode"), "mjera_uvoza": z["mjera_uvoza"], "iz_dopune": z["mjera_iz_dopune"],
                          "cijena": z["odabrana_cijena"], "stupac": z["odabrani_stupac"], "po_jedinici": z["po_jedinici"],
                          "redak": z["odabrani_redak"], "trgovina": z["trgovina_odabranog"], "sve_cijene": z["sve_cijene"][:6]},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
