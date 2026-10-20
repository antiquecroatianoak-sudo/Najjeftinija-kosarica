"""Provjera prepoznavanja količina u dnevnom uvozu: python3 tests/kolicine.py"""
import importlib.util
from pathlib import Path

put = Path(__file__).resolve().parent.parent / "scripts" / "azuriraj_cijene.py"
spec = importlib.util.spec_from_file_location("azuriraj_cijene", put)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

slucajevi = [
    (("310", "g", ""), (0.31, "kg")),
    (("1", "kom", "Čokolada 310g"), (0.31, "kg")),
    (("", "kom", "Pivo 6x0,5l"), (3.0, "l")),
    # Pakiranje zapisano iza količine: cijena je za sva četiri komada.
    (("", "kom", "Jogurt 125 g x 4"), (0.5, "kg")),
    (("", "kom", "Voda 0,5 L x 6"), (3.0, "l")),
    (("", "kom", "Sok 1,5 L 6 kom"), (1.5, "l")),
    (("", "kom", "Ploča 1 kg x 1,5"), (1.0, "kg")),
    (("100", "ml", "Šampon 2x100 ml"), (0.1, "l")),
    (("1", "kg", "Banane"), (1.0, "kg")),
    (("", "kom", "Brašno 1 kg x 100"), None),  # 100 kg premašuje razumnu granicu
]
for ulaz, ocekivano in slucajevi:
    assert a.mjera(*ulaz) == ocekivano, (ulaz, a.mjera(*ulaz), ocekivano)

# Produkcija 20.10.2026.: "KRUH RUSTIKA 310 g PP MLINAR" imao je 31 kg (pogrešan decimalni red u polju ili dopuni).
u = a.uskladi_s_nazivom
assert u((31.0, "kg"), "KRUH RUSTIKA 310 g PP MLINAR", [(31.0, "kg"), (0.31, "kg")]) == (0.31, "kg"), "another chain confirms 310 g"
assert u((0.031, "kg"), "Kruh 310 g", [(0.31, "kg")]) == (0.31, "kg")
# Bez potvrde drugog lanca razlika od 10× može biti valjano pakiranje i ostaje.
assert u((0.055, "kg"), "Kava kapsule Lungo 5,5 g", [(0.055, "kg")]) == (0.055, "kg"), "10 capsules x 5,5 g"
assert u((2.0, "l"), "Sok jabuka 0,2 l", [(2.0, "l")]) == (2.0, "l"), "10-pack of 0,2 l"
assert u((1.25, "kg"), "Jogurt 125 g") == (1.25, "kg")
assert u((31.0, "kg"), "KRUH RUSTIKA 310 g PP MLINAR", [(31.0, "kg")]) == (31.0, "kg"), "unconfirmed: not guessed"
# Ostale razlike ostaju.
assert u((3.0, "l"), "Pivo 0,5 l", [(0.5, "l")]) == (3.0, "l"), "six-pack is not a decimal-order error"
assert u((0.5, "kg"), "Jogurt 125 g x 4") == (0.5, "kg")
assert u((2.0, "kg"), "Brašno glatko") == (2.0, "kg")
assert u((1.0, "l"), "Mlijeko 1 kg", [(1.0, "kg")]) == (1.0, "l")
assert u(None, "Kruh 310 g") is None

# Cijeli uvoz sa sintetičkom arhivom: jedan lanac piše 31 kg, drugi 310 g; kapsule u jednom lancu ostaju 55 g.
import tempfile, zipfile
with tempfile.TemporaryDirectory() as tmp:
    arhiva = Path(tmp) / "test.zip"
    with zipfile.ZipFile(arhiva, "w") as zf:
        zf.writestr("konzum/products.csv", "product_id,barcode,name,brand,quantity,unit\n"
                    "1,385001,KRUH RUSTIKA 310 g PP MLINAR,MLINAR,31,kg\n2,385002,\"Pivo 0,5 l\",,3,l\n"
                    "3,385003,\"Kava kapsule Lungo 5,5 g\",,55,g\n")
        zf.writestr("konzum/prices.csv", "product_id,price,special_price\n1,1.99,\n2,6.00,\n3,3.49,\n")
        zf.writestr("spar/products.csv", "product_id,barcode,name,brand,quantity,unit\n"
                    "9,385001,Kruh Rustika 310g,MLINAR,310,g\n")
        zf.writestr("spar/prices.csv", "product_id,price,special_price\n9,2.09,\n")
    lanci, proizvodi = a.obradi(arhiva)
    po_nazivu = {p[0]: p for p in proizvodi}
    assert po_nazivu["KRUH RUSTIKA 310 g PP MLINAR"][2:4] == [0.31, "kg"], po_nazivu["KRUH RUSTIKA 310 g PP MLINAR"]
    assert po_nazivu["Pivo 0,5 l"][2:4] == [3.0, "l"], "six-pack quantity from the field is kept"
    assert po_nazivu["Kava kapsule Lungo 5,5 g"][2:4] == [0.055, "kg"], "valid 10-pack is not overwritten"
    _, proizvodi = a.obradi(arhiva, {"385001": (31.0, "kg")})
    assert [p for p in proizvodi if p[0].startswith("KRUH")][0][2] == 0.31, "wrong enrichment corrected when a chain confirms"

print("QUANTITY PARSER PASS:", len(slucajevi), "cases")
