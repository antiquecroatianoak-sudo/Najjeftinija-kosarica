"""Cijena lanca iz stvarnih redaka (krumpir, arhiva 2026-10-21), bez mreže: python3 tests/cijene_lanca.py"""
import csv
import importlib.util
import io
import tempfile
import zipfile
from pathlib import Path

put = Path(__file__).resolve().parent.parent / "scripts" / "azuriraj_cijene.py"
spec = importlib.util.spec_from_file_location("azuriraj_cijene", put)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def csv_tekst(retci):
    f = io.StringIO()
    w = csv.DictWriter(f, fieldnames=list(retci[0]))
    w.writeheader()
    w.writerows(retci)
    return f.getvalue()


def arhiva(mapa, lanci):
    put = Path(mapa) / "arhiva.zip"
    with zipfile.ZipFile(put, "w") as zf:
        for lanac, (proizvodi, cijene) in lanci.items():
            zf.writestr(f"{lanac}/products.csv", csv_tekst(proizvodi))
            zf.writestr(f"{lanac}/prices.csv", csv_tekst(cijene))
    return put


def proizvod(pid, naziv, kolicina, jedinica, barkod=""):
    return {"product_id": pid, "barcode": barkod, "name": naziv, "brand": "", "quantity": kolicina, "unit": jedinica}


def cijena(pid, trgovina, price, special="", unit=""):
    return {"store_id": trgovina, "product_id": pid, "price": price, "special_price": special, "unit_price": unit}


# Stvarni retci: Trgovina Krk, "KRUMPIR ZA GASTRO 1 kg" 0,10 € samo u poslovnici set._sv._bernardina_6c_krk,
# ostale poslovnice 0,22-1,09 €. Prije: cijena lanca = najniža poslovnica = 0,10 €/kg (prvi u poretku krumpira).
krk = [cijena("g1", "set._sv._bernardina_6c_krk", "0.10")] + [
    cijena("g1", f"krk_{i}", c) for i, c in enumerate(["0.22", "0.89", "0.99", "0.99", "1.09"])]
# Stvarni redak: NTL "KRUMPIR 2,5 kg SNIŽENJE", količina "2,5", jedinica kom. Prije: 2,5 komada, sad 2,5 kg.
ntl = [cijena("n1", "ntl_1", "1.49")]
# Stvarni redak: Plodine "KRUMPIR 2,5 KG GIRO" 1,11 € uz objavljenu jediničnu cijenu 0,56 €/kg (1,11 / 2,5 = 0,44):
# cijena i jedinična cijena trgovca si proturječe, količina nije potvrđena: ponuda je vidljiva, ali bez poretka.
plodine = [cijena("p1", "plodine_1", "1.11", unit="0.56"), cijena("p2", "plodine_1", "2.20", unit="0.88")]
with tempfile.TemporaryDirectory() as tmp:
    statistika, primjeri = {}, []
    lanci, proizvodi = a.obradi(arhiva(tmp, {
        "trgovina-krk": ([proizvod("g1", "KRUMPIR ZA GASTRO 1 kg", "1", "kg")], krk),
        "ntl": ([proizvod("n1", "KRUMPIR 2,5 kg SNIŽENJE", "2,5", "kom")], ntl),
        "plodine": ([proizvod("p1", "KRUMPIR 2,5 KG GIRO", "1", "KOM"), proizvod("p2", "KRUMPIR MLADI 2,5 KG", "1", "KOM")], plodine),
        # Stvarni redak Boso: "PIVO OŽUJ. 2 L Q-PACK" 4,29 € i 2,15 €/l; dopuna za taj barkod kaže 0,4 kg.
        "boso": ([proizvod("b1", "PIVO OŽUJ. 2 L Q-PACK", "1", "KOM", "3850000000000")],
                 [cijena("b1", "DISK.BOROVO", "4.29", unit="2.15")]),
        "konzum": ([proizvod("k1", "Pivo Ožujsko 2 l", "1", "KOM", "3850000000000")], [cijena("k1", "k_1", "4.49")]),
    }), {"3850000000000": (0.4, "kg")}, statistika=statistika, primjeri=primjeri)
po = {p[0]: p for p in proizvodi}
assert po["KRUMPIR ZA GASTRO 1 kg"][5] == [lanci.index("Trgovina Krk"), 0.89], po["KRUMPIR ZA GASTRO 1 kg"]
assert po["KRUMPIR 2,5 kg SNIŽENJE"][2:4] == [2.5, "kg"], "fractional piece count is not a quantity; the name decides"
assert po["KRUMPIR 2,5 KG GIRO"][2:4] == [0, ""] and po["KRUMPIR 2,5 KG GIRO"][5][1] == 1.11, \
    "quantity contradicting the chain's own unit price: offer shown without unit price, so not ranked"
pivo = [p for p in proizvodi if p[0].lower().startswith("pivo")]
assert len(pivo) == 1 and pivo[0][2:4] == [2.0, "l"] and len(pivo[0][5]) == 4, "chain-confirmed 2 l replaces wrong enrichment 0,4 kg"
assert po["KRUMPIR MLADI 2,5 KG"][5][1] == 2.2, "consistent unit price (2,20 / 2,5 = 0,88) is kept"
assert statistika["Plodine"]["količina nepotvrđena jediničnom cijenom (prikaz bez poretka)"] == 1
assert statistika["Boso"]["količina lanca umjesto dopune (potvrđena jediničnom cijenom)"] == 1
assert statistika["Trgovina Krk"]["najniža poslovnica ispod cijene lanca"] == 1
krk_primjer = next(p for p in primjeri if p["lanac"] == "Trgovina Krk")
assert (krk_primjer["prije"], krk_primjer["poslije"]) == (0.10, 0.89), krk_primjer

# Pravila jedno po jedno.
assert a.cijena_lanca([0.5]) == 0.5 and a.cijena_lanca([1.0, 0.1]) == 0.1 and a.cijena_lanca([0.1, 1.0, 1.0]) == 1.0
assert a.cijena_lanca([0.1, 0.9, 1.0, 1.0]) == 0.9, "lower median: a price at or below which half the stores sell"
ok = lambda **r: a.jedinicna_se_slaze(r, (0.5, "kg"))  # noqa: E731
assert ok(price="1.99", unit_price="3.98") and ok(price="1.99", unit_price="3.99"), "rounding tolerated"
assert ok(price="2.49", special_price="1.99", unit_price="4.98"), "unit price of the regular price is consistent"
assert ok(price="1.99", unit_price="1.99"), "unit price per piece"
assert ok(price="1.99", unit_price="") and ok(price="1.99", unit_price="0.00"), "nothing to compare"
assert not ok(price="1.99", unit_price="2.50")
assert a.jedinicna_se_slaze({"price": "1.99", "unit_price": "9"}, (1, "kom")), "piece goods are not checked"
assert a.mjera("0,5", "kom", "Lubenica") is None, "fractional piece without a quantity in the name is unknown, not 0,5 kom"
print("CHAIN PRICE PASS: lower median of stores (Krk 0,10 → 0,89), fractional kom → name quantity (NTL 2,5 kg), "
      "unconfirmed quantity shown unranked (Plodine 1,11 vs 0,56 €/kg), chain-confirmed quantity over wrong enrichment (Boso beer 2 l), rounding and per-piece unit prices accepted")
