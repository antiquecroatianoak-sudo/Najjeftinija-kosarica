"""Prag šuma: zadržavanje načina baterije i prag troška u usporedbi."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jezgra import konfig  # noqa: E402
from jezgra.jezgra import Jezgra  # noqa: E402
from scenariji import usporedba  # noqa: E402


class TestZadrzavanje(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        cfg = konfig.ucitaj(Path(self.d.name))
        cfg["politika"]["min_trajanje_baterija_s"] = 900
        self.t = [1_800_000_000.0]
        self.j = Jezgra(Path(self.d.name), cfg, sat=lambda: self.t[0])

    def tearDown(self):
        self.j.zatvori()
        self.d.cleanup()

    def test_kratka_promjena_se_zadrzava(self):
        j = self.j
        odl = ("puni", "plan", "plan")
        self.assertEqual(j._zadrzi_bateriju(2000.0, odl, 0.0)[0], 2000.0)
        cmd, o = j._zadrzi_bateriju(None, ("vlastita potrošnja", "x", "plan"), 300.0)
        self.assertEqual(cmd, 2000.0)  # 5 min < 15 min: ostaje punjenje
        self.assertIn("prag šuma", o[1])
        self.assertEqual(j.preklapanja["baterija"], 0)
        cmd, _ = j._zadrzi_bateriju(None, ("vlastita potrošnja", "x", "plan"), 901.0)
        self.assertIsNone(cmd)  # nakon 15 min promjena prolazi
        self.assertEqual(j.preklapanja["baterija"], 1)

    def test_isti_nacin_ne_broji_preklapanje(self):
        j = self.j
        j._zadrzi_bateriju(0.0, ("čuva", "x", "plan"), 0.0)
        j._zadrzi_bateriju(0.0, ("čuva", "x", "plan"), 10.0)
        self.assertEqual(j.preklapanja["baterija"], 0)

    def test_iskljuceno(self):
        self.j.cfg["politika"]["min_trajanje_baterija_s"] = 0
        self.j._zadrzi_bateriju(2000.0, ("puni", "", "plan"), 0.0)
        self.assertIsNone(self.j._zadrzi_bateriju(None, ("auto", "", "plan"), 1.0)[0])


class TestPragTroska(unittest.TestCase):
    @staticmethod
    def _k(trosak):
        return {"trosak_eur": trosak, "bez_tople_vode_min": 0, "stres_biljaka_h": 0.0, "neisporuceno_kwh": 0.0,
                "pastir": 1.0}

    def test_razlika_ispod_praga_je_izjednacenje(self):
        self.assertFalse(usporedba._nadmasuje(self._k(-0.39), self._k(-0.35)))  # 4 centa < 5 centi

    def test_razlika_iznad_praga_se_broji(self):
        self.assertTrue(usporedba._nadmasuje(self._k(-0.50), self._k(-0.35)))

    def test_relativni_prag_za_vece_troskove(self):
        self.assertFalse(usporedba._nadmasuje(self._k(17.00), self._k(17.15)))   # < 1 % od 17,15 €
        self.assertTrue(usporedba._nadmasuje(self._k(17.00), self._k(17.40)))


if __name__ == "__main__":
    unittest.main()
