"""Stres testovi s povijesnim podacima: format API-ja (mokovi), odabir tjedana, simulacija na povijesti."""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jezgra.prognoza import zracenje_vedro  # noqa: E402
from stres import povijest as P  # noqa: E402


def sinteticki_podaci(put: Path, dana: int = 70) -> None:
    """Isti format kao preuzmi(): satno vrijeme + satne burzovne cijene (EUR/kWh)."""
    rng = random.Random(3)
    t0 = int(time.mktime((2025, 1, 6, 0, 0, 0, 0, 0, -1)))
    t = [t0 + i * 3600 for i in range(dana * 24)]
    v = {"t": t, "zracenje": [], "temp": [], "oborine": [], "naoblaka": []}
    cijene = {}
    for i, ts in enumerate(t):
        dan = i // 24
        oblak = 0.95 if 20 <= dan < 27 else rng.uniform(0, 0.8)   # jedan vrlo tamni tjedan
        v["zracenje"].append(round(zracenje_vedro(ts, 45.81, 15.98) * (1 - 0.75 * oblak), 1))
        v["temp"].append(round(2 + 8 * math.sin((i % 24 - 9) / 24 * 2 * math.pi) - (12 if 40 <= dan < 47 else 0), 1))
        v["oborine"].append(round(rng.uniform(0, 2), 1) if rng.random() < 0.05 else 0.0)
        v["naoblaka"].append(int(oblak * 100))
        h = time.localtime(ts).tm_hour
        spot = 0.09 + (0.08 if 17 <= h <= 20 else 0) - (0.05 if 11 <= h <= 14 else 0) + rng.uniform(-0.01, 0.01)
        if 55 <= dan < 62 and 11 <= h <= 14:
            spot = -0.04                                            # tjedan s negativnim cijenama
        cijene[str(ts)] = round(spot, 5)
    put.write_text(json.dumps({"meta": {"od": "2025-01-06", "do": "2025-03-16", "zona_cijena": "TEST",
                                        "izvori": {"vrijeme": "sintetika", "cijene": "sintetika"},
                                        "dodatak_eur_kwh": 0.085}, "vrijeme": v, "cijene": cijene}))


class TestPreuzimanje(unittest.TestCase):
    def test_format_api_odgovora(self):
        arhiva = {"hourly": {"time": [0, 3600], "shortwave_radiation": [0, 120.5], "temperature_2m": [3.1, 4.0],
                             "precipitation": [0, 0.2], "cloud_cover": [80, 60]}}
        cijene_hr = {"unix_seconds": [0, 900, 1800, 2700], "price": [100.0, 120.0, 80.0, 100.0], "unit": "EUR / MWh"}
        pozivi = []

        def lazni_json(url, timeout=60):
            pozivi.append(url)
            if "archive-api.open-meteo.com" in url:
                return arhiva
            if "bzn=HR" in url:
                raise OSError("zona nije podržana")
            return {"unix_seconds": [k * 3600 + j * 900 for k in range(800) for j in range(4)],
                    "price": [100.0, 120.0, 80.0, 100.0] * 800}

        with mock.patch.object(P, "_json", lazni_json), mock.patch.object(P.time, "sleep"):
            v = P.preuzmi_vrijeme("2024-01-01", "2024-01-02")
            zona, c = P.preuzmi_cijene("2024-01-01", "2024-01-31")
        self.assertEqual(v["zracenje"], [0, 120.5])
        self.assertEqual(zona, "SI")                      # HR nije uspio -> sljedeća zona
        self.assertAlmostEqual(c[0], 0.1)                 # 15-min usrednjeno po satu, EUR/MWh -> EUR/kWh
        self.assertTrue(any("bzn=HR" in u for u in pozivi))
        del cijene_hr


class TestStresNaPovijesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        cls.put = str(Path(cls._d.name) / "povijest.json")
        sinteticki_podaci(Path(cls.put))

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def test_odabir_najtezih_tjedana(self):
        tj = dict(P.odaberi_tjedne(P.ucitaj(self.put)))
        lt = lambda ts: (ts - P.ucitaj(self.put)["vrijeme"]["t"][0]) // 86400  # noqa: E731
        self.assertTrue(14 <= lt(tj["najtamniji"]) <= 27)
        self.assertTrue(35 <= lt(tj["najhladniji"]) <= 47)
        self.assertTrue(49 <= lt(tj["najvise_negativnih"]) <= 62)
        self.assertGreaterEqual(len(tj), 7)

    def test_simulacija_na_povijesti_bez_krsenja(self):
        import dataclasses
        from scenariji.pokretac import pokreni
        sc = next(s for s in P.scenariji(self.put) if "najvise_negativnih" in s.ime)
        r = pokreni(dataclasses.replace(sc, dani=2.0, korak_s=180))
        self.assertEqual(r["kpi"]["krsenja"], 0, r["krsenja"])
        self.assertEqual(r["kpi"]["iznimke"], 0)
        self.assertIn("dinamicka", r["kpi"]["tarifa_izvori"])
        from jezgra import konfig
        podaci = P.ucitaj(self.put)
        ts = podaci["vrijeme"]["t"][300]
        lok = P.PovijesnaLokacija(konfig.ZADANO, ts, podaci)
        self.assertEqual(lok.zracenje(ts), podaci["vrijeme"]["zracenje"][300])  # stvarno, ne model


if __name__ == "__main__":
    unittest.main()
