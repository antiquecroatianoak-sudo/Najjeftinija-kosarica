"""
Mjerenje (samo čitanje): koliko bi zauzeli podaci po stvarnoj poslovnici. python scripts/mjera_poslovnica.py

Za svaki lanac: broj poslovnica, proizvoda i redaka; broj različitih cjenika (poslovnice s potpuno istim popisom i
cijenama dijele cjenik); zbroj iznimki u odnosu na najčešću cijenu lanca (drukčija cijena) i proizvoda koji u
poslovnici nema. Procjena veličine datoteke po lancu kad se šalje "najčešća cijena + iznimke po cjeniku".
"""
import hashlib
import json
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import azuriraj_cijene as a  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        arhiva = Path(tmp) / "cijene.zip"
        datum = a.preuzmi_najnoviju_arhivu(arhiva)
        ukupno = Counter()
        with zipfile.ZipFile(arhiva) as zf:
            for lanac in sorted({n.split("/")[0] for n in zf.namelist() if n.endswith("/prices.csv")}):
                if lanac in a.PRESKOCI_LANCE:
                    continue
                po_poslovnici: dict[str, dict[str, float]] = {}
                for red in a.citaj_csv(zf, f"{lanac}/prices.csv"):
                    c = [x for x in (a.cijena_za_uvoz(red["price"]), a.cijena_za_uvoz(red.get("special_price", ""))) if x]
                    if c:
                        po_poslovnici.setdefault(red["store_id"], {})[red["product_id"]] = min(c)
                cjenici = {}
                for s, cj in po_poslovnici.items():
                    h = hashlib.sha1(json.dumps(sorted(cj.items())).encode()).hexdigest()
                    cjenici.setdefault(h, cj)
                glasovi: dict[str, Counter] = {}
                for cj in po_poslovnici.values():
                    for pid, c in cj.items():
                        glasovi.setdefault(pid, Counter())[c] += 1
                mod = {pid: g.most_common(1)[0][0] for pid, g in glasovi.items()}
                iznimke = sum(1 for cj in cjenici.values() for pid, c in cj.items() if mod[pid] != c)
                nedostaje = sum(len(mod) - len(cj) for cj in cjenici.values())
                prisutno = sum(len(cj) for cj in cjenici.values())
                # Procjena: indeks ~6 B + cijena ~6 B po iznimci; nedostajući ~6 B; osnovna cijena ~7 B po proizvodu.
                bajtova = 7 * len(mod) + 12 * iznimke + 6 * min(nedostaje, prisutno)
                st = {"poslovnica": len(po_poslovnici), "cjenika": len(cjenici), "proizvoda": len(mod),
                      "redaka": sum(len(cj) for cj in po_poslovnici.values()), "iznimki_cijene": iznimke,
                      "nedostaje": nedostaje, "procjena_kB": round(bajtova / 1000)}
                ukupno.update({k: v for k, v in st.items()})
                print(f"{lanac}: " + json.dumps(st), flush=True)
        print(f"Arhiva {datum} ukupno: " + json.dumps(dict(ukupno)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
