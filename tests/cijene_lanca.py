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
# ostale poslovnice 0,22-1,09 €. Cijena lanca je stvarna cijena te jedne poslovnice i nosi tu poslovnicu i raspon
# ostalih (oznaka za provjeru, ne dokaz greške).
krk = [cijena("g1", "set._sv._bernardina_6c_krk", "0.10")] + [
    cijena("g1", f"krk_{i}", c) for i, c in enumerate(["0.22", "0.89", "0.99", "0.99", "1.09"])]
# Stvarni redak: NTL "KRUMPIR 2,5 kg SNIŽENJE", količina "2,5", jedinica kom. Prije: 2,5 komada, sad 2,5 kg.
ntl = [cijena("n1", "ntl_1", "1.49")]
# Stvarni redak: Plodine "KRUMPIR 2,5 KG GIRO" 1,11 € uz objavljenu jediničnu cijenu 0,56 €/kg (1,11 / 2,5 = 0,44):
# cijena i jedinična cijena trgovca si proturječe, količina nije potvrđena: ponuda je vidljiva, ali bez poretka.
# KRUMPIR MLADI: akcijska 2,20 € uz jediničnu 0,88 €/kg (= 2,20 / 2,5) pripada akcijskom polju.
plodine = [cijena("p1", "plodine_1", "1.11", unit="0.56"), cijena("p2", "plodine_1", "2.49", "2.20", unit="0.88"),
           cijena("p2", "plodine_2", "2.49", unit="9.99")]
with tempfile.TemporaryDirectory() as tmp:
    statistika, primjeri = {}, []
    rez = a.obradi_sve(arhiva(tmp, {
        "trgovina-krk": ([proizvod("g1", "KRUMPIR ZA GASTRO 1 kg", "1", "kg")], krk),
        "ntl": ([proizvod("n1", "KRUMPIR 2,5 kg SNIŽENJE", "2,5", "kom")], ntl),
        "plodine": ([proizvod("p1", "KRUMPIR 2,5 KG GIRO", "1", "KOM"), proizvod("p2", "KRUMPIR MLADI 2,5 KG", "1", "KOM")], plodine),
        # Stvarni redak Boso: "PIVO OŽUJ. 2 L Q-PACK" 4,29 € i 2,15 €/l; dopuna za taj barkod kaže 0,4 kg.
        "boso": ([proizvod("b1", "PIVO OŽUJ. 2 L Q-PACK", "1", "KOM", "3850000000000")],
                 [cijena("b1", "DISK.BOROVO", "4.29", unit="2.15")]),
        "konzum": ([proizvod("k1", "Pivo Ožujsko 2 l", "1", "KOM", "3850000000000")], [cijena("k1", "k_1", "4.49")]),
    }), {"3850000000000": (0.4, "kg")}, statistika=statistika, primjeri=primjeri)
lanci, proizvodi, poslovnice = rez["lanci"], rez["proizvodi"], rez["poslovnice"]
po = {p[0]: p for p in proizvodi}
gastro = po["KRUMPIR ZA GASTRO 1 kg"]
assert gastro[2:4] == [1.0, "kg"] and gastro[5] == [lanci.index("Trgovina Krk"), 0.1], gastro
assert poslovnice[gastro[6][0][0]][1] == "set._sv._bernardina_6c_krk" and gastro[6][0][1:] == [6, 1.09, 0], \
    "the price carries its real store, the number of stores and the highest price (range indicator only)"
assert po["KRUMPIR 2,5 kg SNIŽENJE"][2:4] == [2.5, "kg"], "fractional piece count is not a quantity; the name decides"
assert po["KRUMPIR 2,5 KG GIRO"][2:4] == [0, ""] and po["KRUMPIR 2,5 KG GIRO"][5][1] == 1.11, \
    "quantity contradicting the chain's own unit price: offer shown without unit price, so not ranked"
mladi = po["KRUMPIR MLADI 2,5 KG"]
assert mladi[5][1] == 2.2 and mladi[6][0][3] == 1 and mladi[6][0][1] == 1, \
    "unit price belongs to the special price; the other store's row contradicts and is left out"
pivo = [p for p in proizvodi if p[0].lower().startswith("pivo")]
assert len(pivo) == 1 and pivo[0][2:4] == [2.0, "l"] and len(pivo[0][5]) == 4, "chain-confirmed 2 l replaces wrong enrichment 0,4 kg"
assert statistika["Plodine"]["količina nepotvrđena jediničnom cijenom (prikaz bez poretka)"] == 1
assert statistika["Plodine"]["redak proturječan jediničnoj cijeni (ne rangira se, nije u zbroju poslovnice)"] == 1
assert statistika["Boso"]["količina lanca umjesto dopune (potvrđena jediničnom cijenom)"] == 1
assert sum(s["količina lanca umjesto dopune (potvrđena jediničnom cijenom)"] for s in statistika.values()) == 1
# Cijene po stvarnoj poslovnici: svaka poslovnica ima samo svoje valjane cijene.
i_mladi = proizvodi.index(mladi)
po_s = {poslovnice[s][1]: dict(zip(cj[0::3], cj[1::3])) for s, cj in rez["po_poslovnici"].items()}
assert po_s["plodine_1"][i_mladi] == 220 and i_mladi not in po_s.get("plodine_2", {}), po_s
assert sorted(po_s["krk_0"].values()) == [22] and po_s["set._sv._bernardina_6c_krk"] == {proizvodi.index(gastro): 10}
# Pokrivenost: izvor je cijene.dev, nijedna ponuda nije provjerena prema službenom izvoru.
pok = a.pokrivenost(rez, statistika, "2026-10-21")
assert pok["provjereno_prema_sluzbenom_izvoru"] == 0 and pok["lanci"]["Plodine"]["neprovjereno"] == 2, pok
assert pok["ukupno_ponuda"] == sum(len(p[5]) // 2 for p in proizvodi)

# Stvarni retci Trgocentar: isti deterdžent 12,66 / 7047,06 / 8223,53 € u tri poslovnice, jedinične 14894,12 i jednake
# cijeni. Jedinična 14894,12 €/l odgovara nazivu "0,850ML" (12,66 / 0,00085 l), pa je to količina koju lanac sam
# objavljuje; jedinične jednake cijeni pakiranja nisu provjerljive (ni potvrda ni proturječje). Cijena je stvarna
# najniža (12,66 €), a raspon do 8223,53 € ostaje oznaka za provjeru.
# Konzum "KUPINA 125 grama", količina 0.13 kg, jedinična 22,32 €/kg = 2,79 / 0,125: potvrđuje količina iz naziva.
with tempfile.TemporaryDirectory() as tmp:
    _, proizvodi2 = a.obradi(arhiva(tmp, {
        "trgocentar": ([proizvod("t1", "ARIEL TEK.DET.SENS 0,850ML /17 PRANJA", "0.850 L", "L")],
                       [cijena("t1", "1", "12.66", unit="14894.12"), cijena("t1", "2", "7047.06", unit="7047.06"),
                        cijena("t1", "3", "8223.53", unit="8223.53")]),
        "konzum": ([proizvod("k2", "KUPINA 125 grama", "0.13 kg", "ko")], [cijena("k2", "k_1", "2.79", unit="22.32")]),
    }))
po2 = {p[0]: p for p in proizvodi2}
ariel = po2["ARIEL TEK.DET.SENS 0,850ML /17 PRANJA"]
assert ariel[5][1] == 12.66 and ariel[6][0][1:3] == [3, 8223.53], ariel
assert po2["KUPINA 125 grama"][2:4] == [0.125, "kg"], "name quantity confirmed by the chain's unit price"

# Pravila jedno po jedno.
ok = lambda **r: a.jedinicna_se_slaze(r, (0.5, "kg"))  # noqa: E731
assert ok(price="1.99", unit_price="3.98") and ok(price="1.99", unit_price="3.99"), "rounding tolerated"
assert ok(price="2.49", special_price="1.99", unit_price="4.98"), "unit price of the regular price is consistent"
assert a.polje_jedinicne({"price": "1.99", "unit_price": "1.99"}, (0.5, "kg")) == "", \
    "unit price equal to a 0,5 kg pack price: neither confirmation nor contradiction (not checkable)"
assert a.polje_jedinicne({"price": "2.49", "special_price": "1.99", "unit_price": "3.98"}, (0.5, "kg")) == "special_price"
assert a.polje_jedinicne({"price": "2.49", "special_price": "1.99", "unit_price": "4.98"}, (0.5, "kg")) == "price"
assert a.polje_jedinicne({"price": "2.49", "unit_price": ""}, (0.5, "kg")) == ""
assert ok(price="1.99", unit_price="") and ok(price="1.99", unit_price="0.00"), "nothing to compare"
assert not ok(price="1.99", unit_price="2.50")
assert a.jedinicna_se_slaze({"price": "1.99", "unit_price": "9"}, (1, "kom")), "piece goods are not checked"
assert a.mjera("0,5", "kom", "Lubenica") is None, "fractional piece without a quantity in the name is unknown, not 0,5 kom"
print("CHAIN PRICE PASS: real store price with its store (Krk 0,10 € at set._sv._bernardina_6c_krk, range 1,09 € as "
      "indicator), fractional kom → name quantity (NTL 2,5 kg), unconfirmed quantity unranked (Plodine 1,11 vs 0,56 €/kg), "
      "unit price tied to regular/special field, unit = pack price not checkable (no confirmation), per-store valid prices only, "
      "coverage 0 verified against official source, Boso beer 2 l, Trgocentar contradicting rows left out, Konzum 125 g")

# Stvarna marka iz cjenika ide u "marke" (indeks u p[7]); bez marke u cjeniku -1 (filtar "Samo ova marka" je ne prihvaća).
with tempfile.TemporaryDirectory() as tmp:
    sa_markom = dict(proizvod("d1", "Dukat Mlijeko 2,8% 1 l", "1", "l"), brand="Dukat")
    rez = a.obradi_sve(arhiva(tmp, {"konzum": ([sa_markom, proizvod("d2", "Mlijeko 1 l", "1", "l")],
                                               [cijena("d1", "k1", "1.29"), cijena("d2", "k1", "0.99")])}))
    marke = {p[0]: (rez["marke"][p[7]] if p[7] >= 0 else None) for p in rez["proizvodi"]}
    assert marke == {"Dukat Mlijeko 2,8% 1 l": "Dukat", "Mlijeko 1 l": None}, marke
print("MARKA PASS: stvarna marka iz cjenika, nepoznata = -1")
