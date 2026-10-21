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
    # Stvarni redak NTL (2026-10-21): "2,5" kom nije količina, u nazivu piše 2,5 kg.
    (("2,5", "kom", "KRUMPIR 2,5 kg SNIŽENJE"), (2.5, "kg")),
    (("0,5", "kom", "Lubenica"), None),
    (("", "kom", "KUPINA 125 grama"), (0.125, "kg")),
]
for ulaz, ocekivano in slucajevi:
    assert a.mjera(*ulaz) == ocekivano, (ulaz, a.mjera(*ulaz), ocekivano)
print("QUANTITY PARSER PASS:", len(slucajevi), "cases")
