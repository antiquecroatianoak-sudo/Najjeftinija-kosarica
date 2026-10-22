"""Zaštita objave: stariji ili bitno slabiji cjenik ne zamjenjuje objavljeni. python3 tests/provjera_objave.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import provjera_objave as po  # noqa: E402

objavljeno = {"datum": "2026-10-22", "provjereno_prema_sluzbenom_izvoru": 384989, "ukupno_ponuda": 415645}
slucajevi = [
    # Isti dan iz službenih cjenika (prije 8:00 jučerašnji): dopušteno.
    ({"datum": "2026-10-22", "provjereno_prema_sluzbenom_izvoru": 380000, "ukupno_ponuda": 410000}, True),
    # Novi dan, puni službeni: dopušteno.
    ({"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 390000, "ukupno_ponuda": 420000}, True),
    # Današnji cjenici još nisu objavljeni: samo arhiva, bez potvrđenih -> zaustavljeno.
    ({"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 0, "ukupno_ponuda": 400000}, False),
    # Djelomično (mrežni kvar): ispod polovice potvrđenih -> zaustavljeno.
    ({"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 150000, "ukupno_ponuda": 400000}, False),
    # Raniji dan od objavljenoga -> zaustavljeno.
    ({"datum": "2026-10-21", "provjereno_prema_sluzbenom_izvoru": 390000, "ukupno_ponuda": 420000}, False),
]
for novo, ocekivano in slucajevi:
    smije, razlog = po.odluka(objavljeno, novo)
    assert smije is ocekivano, (novo, razlog)
# Objavljeni nedostupan (prva objava / mreža): samo uz potvrđene ponude.
assert po.odluka(None, slucajevi[0][0])[0] is True
assert po.odluka(None, slucajevi[2][0])[0] is False
# Objavljeni bez potvrđenih (stari oblik): novi bez potvrđenih ne pogoršava stanje.
assert po.odluka({"datum": "2026-10-20", "provjereno_prema_sluzbenom_izvoru": 0}, slucajevi[2][0])[0] is True
print("OBJAVA PASS: isti/novi dan dopušten; bez potvrđenih, ispod 50 % ili raniji dan zaustavljeno; nedostupan objavljeni samo uz potvrđene")
