"""Spremnik PTV-a: toplinski model, MPC s dizalicom topline, ciklus protiv legionele."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lokalno_vrijeme  # noqa: E402,F401  (zona simulirane lokacije)

from jezgra import konfig  # noqa: E402
from jezgra.anomalije import Detektor  # noqa: E402
from jezgra.spremnik import Legionela, ModelSpremnika, cop, planiraj, zadano  # noqa: E402


def cijene(jeftino_sati, H=36, jeftino=0.08, skupo=0.30):
    return [{"kupnja": jeftino if (h % 24) in jeftino_sati else skupo, "prodaja": 0.05} for h in range(H)]


class TestModel(unittest.TestCase):
    def test_gubici_bez_potrosnje(self):
        m = ModelSpremnika(zadano())
        t, el = m.korak(55.0, 10.0, False, False, 0.0, 10.0)
        # 1,5 W/K · ~36 K · 10 h ≈ 0,55 kWh -> ~3 K pada na 150 L
        self.assertAlmostEqual(55.0 - t, 1.5 * (55 - 18) * 10 / 1000 / m.c_kwh_k, delta=0.3)
        self.assertEqual(el, 0.0)

    def test_dizalica_ne_ide_preko_granice_grijac_ide(self):
        m = ModelSpremnika(zadano())
        t, _ = m.korak(54.0, 3.0, True, False, 0.0, 10.0)
        self.assertLessEqual(t, 55.0 + 1e-6)
        t, _ = m.korak(54.0, 3.0, False, True, 0.0, 10.0)
        self.assertGreater(t, 60.0)
        self.assertLessEqual(t, 65.0 + 1e-6)

    def test_cop_pada_s_temperaturom_vode(self):
        self.assertGreater(cop(30, 15), cop(55, 15))
        self.assertGreater(cop(45, 25), cop(45, 0))

    def test_ucenje_gubitaka_iz_mirnih_razdoblja(self):
        m = ModelSpremnika(zadano())  # pretpostavka 1,5 W/K
        stvarni_ua, c = 2.4, m.c_kwh_k
        t, ts = 58.0, time.mktime((2026, 3, 2, 0, 0, 0, 0, 0, -1))
        for _ in range(4 * 24 * 60):  # 4 dana, korak 1 min, osjetnik na 0,1 °C
            t -= stvarni_ua * (t - 18.0) / 1000 / 60 / c
            if t < 45:
                t = 58.0  # (grijanje izvan mirnog razdoblja)
                m.uci(ts, round(t, 1), 1.0, 60, mirno=False)
            else:
                m.uci(ts, round(t, 1), 0.0, 60, mirno=True)
            ts += 60
        self.assertGreater(m.ua_uzoraka, 5)
        self.assertAlmostEqual(m.ua, stvarni_ua, delta=0.35)


class TestPlaner(unittest.TestCase):
    def setUp(self):
        self.m = ModelSpremnika(zadano())
        self.pris = [7 <= (h % 24) <= 22 for h in range(36)]
        self.potr = self.m.prognoza_potrosnje(time.mktime((2026, 3, 2, 0, 0, 0, 0, 0, -1)), 36, self.pris)

    def test_predgrijava_u_jeftinim_satima_dizalicom(self):
        plan = planiraj(self.m, 40.0, cijene({0, 1, 2, 3, 4, 5}), [0] * 36, [10] * 36, self.pris, self.potr, None)
        jeftini = [h for h in range(6) if plan[h]["dizalica"]]
        self.assertTrue(jeftini, "nema predgrijavanja u jeftinim satima")
        self.assertGreaterEqual(plan[5]["t_kraj"], 50.0)
        self.assertFalse(any(x["grijac"] for x in plan[:24]), "grijač bez potrebe (prednost dizalici)")

    def test_udobnost_dok_su_stanari_tu(self):
        plan = planiraj(self.m, 40.0, cijene({0, 1, 2, 3, 4, 5}), [0] * 36, [10] * 36, self.pris, self.potr, None)
        for h in range(36):
            if self.pris[h]:
                self.assertGreaterEqual(plan[h]["t_kraj"], 44.0, h)

    def test_legionela_do_roka_u_najjeftinijem_satu(self):
        c = cijene({2, 3})
        c[13] = {"kupnja": 0.02, "prodaja": 0.0}
        plan = planiraj(self.m, 50.0, c, [0] * 36, [10] * 36, self.pris, self.potr, 20, 62.0)
        sati = [h for h, x in enumerate(plan) if x["legionela"]]
        self.assertEqual(len(sati), 1)
        self.assertLessEqual(sati[0], 20)
        h = sati[0]
        self.assertGreaterEqual(plan[h]["t_kraj"], 60.0)
        self.assertGreaterEqual(plan[h - 1]["t_kraj"], 60.0)  # cijeli sat ≥ 60 °C
        self.assertTrue(any(plan[k]["grijac"] for k in range(max(0, h - 3), h + 1)))

    def test_visak_sunca_je_jeftin(self):
        pv = [3000.0 if 10 <= (h % 24) <= 14 else 0.0 for h in range(36)]
        plan = planiraj(self.m, 46.0, cijene(set()), pv, [15] * 36, self.pris, self.potr, None)
        self.assertTrue(any(plan[h]["dizalica"] for h in range(10, 15)))


class TestLegionela(unittest.TestCase):
    def setUp(self):
        self.c = ModelSpremnika(zadano()).c_kwh_k
        self.ts = 1_800_000_000.0
        self.l = Legionela(zadano()["legionela"], sada=self.ts)
        self.l.zadnja = self.ts - 7 * 86400  # rok istekao

    def test_uspjesan_ciklus(self):
        for _ in range(31):
            self.l.korak(self.ts, 60, 61.5, self.c)
            self.ts += 60
        self.assertEqual(self.l.ciklusa, 1)
        self.assertGreater(self.l.rok_h(self.ts), 24 * 6)
        self.assertEqual(self.l.dogadjaji[-1]["vrsta"], "legionela_ok")

    def test_pad_zbog_potrosnje_je_gubitak_i_nadoknada(self):
        for _ in range(10):
            self.l.korak(self.ts, 60, 61.0, self.c)
            self.ts += 60
        self.l.korak(self.ts, 60, 55.0, self.c)  # tuš usred ciklusa
        d = self.l.dogadjaji[-1]
        self.assertEqual(d["vrsta"], "legionela_gubitak")
        self.assertEqual(d["ozbiljnost"], "info")  # nije greška sustava
        self.assertGreater(self.l.gubitak_kwh, 0.5)
        self.assertEqual(self.l.prekinutih, 1)
        self.assertGreater(self.l.cilj_c, 62.0)  # sljedeći ciklus nadoknađuje
        self.assertTrue(self.l.aktivno(self.ts))  # ciklus ostaje dužan
        for _ in range(31):
            self.l.korak(self.ts, 60, self.l.cilj_c, self.c)
            self.ts += 60
        self.assertEqual(self.l.ciklusa, 1)
        self.assertEqual(self.l.nadoknada_c, 0.0)

    def test_pad_temperature_nije_anomalija(self):
        d = Detektor(konfig.ZADANO)
        for i in range(200):
            d.obradi({"bojler_temp_c": 62.0 if i < 150 else 41.0}, 60)
        self.assertFalse([k for k in d.aktivne if k.startswith("bojler_temp")])


class TestJezgraSpremnik(unittest.TestCase):
    def test_simulacija_dizalica_legionela_udobnost(self):
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        from jezgra.simulacija import Lokacija, izravni_uredaji
        with tempfile.TemporaryDirectory() as d:
            cfg = konfig.ucitaj(Path(d))
            poc = time.mktime((2026, 3, 16, 0, 0, 0, 0, 0, -1))
            lok = Lokacija(cfg, poc, kvarovi=False)
            sat = SimSat(poc)
            j = Jezgra(Path(d), cfg, sat=sat, uredaji=izravni_uredaji(lok),
                       dohvati_prognozu=lambda ts: lok.prognoza_api(ts), dohvati_tarife=lambda ts: lok.tarife_api(ts))
            el = {"d": 0.0, "g": 0.0}
            for _ in range(int(8 * 86400 / 120)):
                lok.korak(120)
                sat.t = lok.t
                j.korak()
                el["d"] += lok.dizalica_w * 120 / 3.6e6
                el["g"] += lok.bojler_w * 120 / 3.6e6
            j.zatvori()
        self.assertEqual(lok.bez_tople_vode_min, 0)
        self.assertLessEqual(lok.legionela_max_razmak_dana(), 7.5)  # stvarna dezinfekcija (mjeri simulator)
        self.assertGreaterEqual(j.legionela.ciklusa, 1)
        self.assertGreater(el["d"], el["g"] * 0.8)  # dizalica topline nosi većinu grijanja
        self.assertAlmostEqual(j.spremnik.ua, lok.spremnik_ua, delta=0.4)  # naučeni gubici


if __name__ == "__main__":
    unittest.main()
