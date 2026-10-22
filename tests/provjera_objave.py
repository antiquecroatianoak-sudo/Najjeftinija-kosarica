"""Zaštita objave: stariji ili bitno slabiji cjenik ne zamjenjuje objavljeni; uski oporavak preranog cjenika.
python3 tests/provjera_objave.py"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import provjera_objave as po  # noqa: E402

ZG = ZoneInfo("Europe/Zagreb")
PRIJE_8 = datetime(2026, 10, 23, 1, 30, tzinfo=ZG)   # očekivani službeni dan 22.10.
POSLIJE_8 = datetime(2026, 10, 23, 9, 17, tzinfo=ZG)  # očekivani službeni dan 23.10.
assert po.ocekivani_dan(PRIJE_8) == "2026-10-22" and po.ocekivani_dan(POSLIJE_8) == "2026-10-23"
assert po.ocekivani_dan(datetime(2026, 10, 23, 5, 59, tzinfo=ZoneInfo("UTC"))) == "2026-10-22", "07:59 Zagreb (CEST) is before 8"

PUN_22 = {"datum": "2026-10-22", "provjereno_prema_sluzbenom_izvoru": 384989, "ukupno_ponuda": 415645}
PUN_23 = {"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 390000, "ukupno_ponuda": 420000}
RANI_23 = {"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 19350, "ukupno_ponuda": 451481}  # stvarni run 39865778942
SLAB_23 = {"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 150000, "ukupno_ponuda": 400000}
BEZ_23 = {"datum": "2026-10-23", "provjereno_prema_sluzbenom_izvoru": 0, "ukupno_ponuda": 400000}
PUN_21 = {"datum": "2026-10-21", "provjereno_prema_sluzbenom_izvoru": 390000, "ukupno_ponuda": 420000}


def provjeri(objavljeno, novo, sada, ocekivano, kako, **kw):
    smije, razlog = po.odluka(objavljeno, novo, sada, **kw)
    assert smije is ocekivano, (kako, razlog)
    return razlog


# Uobičajeno: isti ili novi dan s usporedivim obuhvatom.
provjeri(PUN_22, dict(PUN_22, provjereno_prema_sluzbenom_izvoru=380000), PRIJE_8, True, "same day")
provjeri(PUN_22, PUN_23, POSLIJE_8, True, "new day after 8")
# Zaštita: bez potvrđenih, ispod 50 %, raniji dan.
provjeri(PUN_22, BEZ_23, POSLIJE_8, False, "no confirmed")
provjeri(PUN_22, SLAB_23, POSLIJE_8, False, "below 50 %")
provjeri(PUN_22, PUN_21, PRIJE_8, False, "older day")
# Uski oporavak: objavljen prerani 23.10. (19 350 potvrđenih), prije 8:00 novi puni 22.10. -> dopušteno.
r = provjeri(RANI_23, dict(PUN_22, provjereno_prema_sluzbenom_izvoru=380000), PRIJE_8, True, "bounded recovery")
assert "oporavak preranog cjenika" in r
# Isti prijelaz bez opravdanja ostaje odbijen:
provjeri(RANI_23, PUN_22, POSLIJE_8, False, "after 8 the expected day is 23.10: 22.10 is just older")
provjeri(RANI_23, dict(PUN_22, provjereno_prema_sluzbenom_izvoru=10000), PRIJE_8, False, "recovery must increase coverage")
provjeri(RANI_23, PUN_21, PRIJE_8, False, "21.10 is not the expected day")
provjeri(PUN_23, PUN_22, PRIJE_8, False, "published full 23.10 has more confirmed offers: no recovery")
# Objavljeni nedostupan (mreža): zaustavljeno; samo izričit ručni način i uz potvrđene ponude.
provjeri(None, PUN_22, PRIJE_8, False, "baseline unavailable")
provjeri(None, PUN_22, PRIJE_8, True, "manual first publish", bez_usporedbe=True)
provjeri(None, BEZ_23, PRIJE_8, False, "manual, but nothing confirmed", bez_usporedbe=True)
print("OBJAVA PASS: isti/novi dan dopušten; bez potvrđenih, ispod 50 %, raniji dan zaustavljeno; oporavak 23.10 (19 350) → "
      "22.10 (380 000) prije 8:00 dopušten, isti prijelaz poslije 8:00 / bez porasta / drugi dan odbijen; bez objavljenog "
      "baselinea zaustavljeno osim izričitog ručnog načina s potvrđenim ponudama")
