"""Testovi dnevnog uvoza na primjeru arhive sa zamkama iz stvarnih cjenika.   python -m unittest tests/test_uvoz.py"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

KORIJEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORIJEN / "uvoz"))
sys.path.insert(0, str(KORIJEN / "tests"))

import primjer  # noqa: E402
import uvoz  # noqa: E402
from kolicina import barkod, iz_polja, iz_teksta, odaberi_kolicinu  # noqa: E402


def ucitaj_cijene(lanci, proizvodi):
    """lanac -> {barkod ili naziv: (uobičajena, min, max, redovna)}"""
    out = {}
    for lanac, d in lanci.items():
        i, m = 0, {}
        for k, delta in enumerate(d["i"]):
            i += delta
            p = proizvodi[i]
            m[p[6] or p[0]] = (d["t"][k], d["t"][k] - d["n"][k], d["t"][k] + d["x"][k], d["r"][k])
        out[lanac] = m
    return out


class Kolicine(unittest.TestCase):
    def test_tekst(self):
        self.assertEqual(iz_teksta("Voda 6x1,5 l"), (9.0, "l"))
        self.assertEqual(iz_teksta("Jogurt 4 x 125 g"), (0.5, "kg"))
        self.assertEqual(iz_teksta("125g x 4"), (0.5, "kg"))
        self.assertEqual(iz_teksta("Kruh 500 g"), (0.5, "kg"))
        self.assertEqual(iz_teksta("Mlijeko 2,8% m.m. 1L"), (1.0, "l"))
        self.assertEqual(iz_teksta("Jaja 10 kom"), (10.0, "kom"))
        self.assertIsNone(iz_teksta("Kruh polubijeli"))
        self.assertIsNone(iz_teksta("Vreće 500 kg"))   # apsurdno

    def test_polja(self):
        self.assertEqual(iz_polja("500", "g"), (0.5, "kg"))
        self.assertEqual(iz_polja("0,5", "L"), (0.5, "l"))
        self.assertEqual(iz_polja("1L", ""), (1.0, "l"))
        self.assertIsNone(iz_polja("", "kg"))
        self.assertIsNone(iz_polja("2", "m"))     # nepoznata jedinica: ne izmišljamo pretvorbu

    def test_odabir_s_jedinicnom_cijenom(self):
        # polje kaže 31 kg, naziv 310 g, jedinična cijena potvrđuje 0,31 kg
        self.assertEqual(odaberi_kolicinu((31.0, "kg"), (0.31, "kg"), None, (0.31, "kg")), ((0.31, "kg"), "naziv"))
        # ništa se ne slaže s jediničnom cijenom: količina je nepoznata
        self.assertEqual(odaberi_kolicinu((31.0, "kg"), None, None, (0.31, "kg")), (None, "neslaganje"))
        # bez jedinične cijene, polje i naziv se ne slažu: nepoznato
        self.assertEqual(odaberi_kolicinu((31.0, "kg"), (0.31, "kg"), None, None), (None, "neslaganje"))

    def test_naziv_bez_kolicine(self):
        from kolicina import naziv_bez_kolicine as f
        kg1, l2 = (1.0, "kg"), (2.0, "l")
        self.assertEqual(f("Šećer kristal Agragold 1 kg", kg1), f("Secer kristal, Agragold 1kg", kg1))
        self.assertEqual(f("Coca-Cola 2L", l2), f("Coca cola 2l", l2))
        self.assertEqual(f("Voda 6x1,5 l Jana", (9.0, "l")), "voda jana")
        self.assertNotEqual(f("Mlijeko 2,8% m.m. 1 l", (1.0, "l")), f("Mlijeko 3,5% m.m. 1l", (1.0, "l")))
        self.assertNotEqual(f("Brašno T-400 1kg", kg1), f("Brašno T-850 1 kg", kg1))
        # količina u nazivu koja NIJE količina pakiranja ostaje (kuhalo 1,7 l i 1,8 l, pakiranje 1 kom)
        self.assertNotEqual(f("Kuhalo za vodu 1,8 l", (1.0, "kom")), f("Kuhalo za vodu 1,7 l", (1.0, "kom")))

    def test_barkod(self):
        self.assertEqual(barkod("385010400001"), "0385010400001")
        self.assertIsNone(barkod("konzum:123"))
        self.assertIsNone(barkod("0000000000000"))
        self.assertIsNone(barkod("123"))


def _indeksi(d):
    i, out = 0, set()
    for delta in d["i"]:
        i += delta
        out.add(i)
    return out


class Uvoz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        arhive, koord = primjer.napravi_sve(t / "ulaz")
        (t / "prije.json").write_text(json.dumps({"proizvoda": 40, "lanci": [{"id": "ntl", "proizvoda": 50}]}))
        rc = uvoz.main(["--arhiva", *map(str, arhive), "--izlaz", str(t / "izlaz"), "--bez-dopune",
                        "--prethodni", str(t / "prije.json"), "--privremeno", str(t / "tmp"), "--izvjesce", str(t / "greska.md")])
        assert rc == 0, (t / "greska.md").read_text()
        # i još jednom s koordinatama
        rc = uvoz.main(["--arhiva", *map(str, arhive), "--izlaz", str(t / "izlaz2"), "--dopuna-poslovnica", str(koord),
                        "--dopuna-proizvoda", str(t / "nema.csv"), "--privremeno", str(t / "tmp")])
        assert rc == 0
        cls.arhive, cls.t = arhive, t
        cls.meta = json.loads((t / "izlaz/meta.json").read_text())
        cls.pr = json.loads((t / "izlaz/proizvodi.json").read_text())
        cls.pos = json.loads((t / "izlaz/poslovnice.json").read_text())
        cls.grupe = json.loads((t / "izlaz/grupe.json").read_text())["grupe"]
        cls.cijene = ucitaj_cijene(cls.pr["l"], cls.pr["p"])
        cls.po_barkodu = {p[6]: p for p in cls.pr["p"] if p[6]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def grupa(self, bk):
        p = self.po_barkodu[bk]
        g = self.grupe[p[4]] if p[4] >= 0 else None
        return (g["id"] if g else None, g["pod"][p[5]]["id"] if g and p[5] >= 0 else None)

    def test_kolicina_310g_ne_31kg(self):
        p = self.po_barkodu["3850104000066"]
        self.assertEqual((p[2], p[3]), (0.31, "kg"))

    def test_visestruko_pakiranje(self):
        p = self.po_barkodu["3850116000018"]
        self.assertEqual((p[2], p[3]), (9.0, "l"))

    def test_nema_duplikata(self):
        barkodovi = [p[6] for p in self.pr["p"] if p[6]]
        self.assertEqual(len(barkodovi), len(set(barkodovi)))
        bez = [p for p in self.pr["p"] if p[0].startswith("Domaći kruh")]
        self.assertEqual(len(bez), 1, "isti proizvod bez barkoda u dva lanca treba biti jedan")
        # isti proizvod pod dva barkoda u dva lanca: jedan proizvod, oba barkoda, cijene oba lanca
        agr = [p for p in self.pr["p"] if "Agragold" in p[1]]
        self.assertEqual(len(agr), 1, agr)
        self.assertEqual({agr[0][6], *agr[0][7].split(",")}, {"9007829021019", "9007829025017"})
        gi = self.pr["p"].index(agr[0])
        u_lancima = [l for l, d in self.pr["l"].items() if gi in _indeksi(d)]
        self.assertEqual(sorted(u_lancima), ["kaufland", "konzum"])
        lanci = [l for l, m in self.cijene.items() if "Domaći kruh 600 g" in m]
        self.assertIn("plodine", lanci)
        self.assertIn("spar", lanci)

    def test_lose_cijene(self):
        # 100× preskupo u jednoj Konzumovoj poslovnici ne smije ući u raspon
        t, mn, mx, _ = self.cijene["konzum"]["3850108000021"]
        self.assertLess(mx, t * 1.2)
        self.assertGreaterEqual(self.meta["preskoceno"].get("cijena odstupa od uobičajene", 0), 1)
        self.assertGreaterEqual(self.meta["preskoceno"].get("neispravna cijena", 0), 1)
        for lanac, m in self.cijene.items():
            for k, (t, mn, mx, r) in m.items():
                self.assertGreater(mn, 1, (lanac, k))

    def test_akcija(self):
        akcije = [(l, k) for l, m in self.cijene.items() for k, v in m.items() if v[3] > v[0]]
        self.assertTrue(akcije)

    def test_stari_podaci_za_lanac_koji_nedostaje(self):
        ntl = next(l for l in self.meta["lanci"] if l["id"] == "ntl")
        self.assertEqual(ntl["status"], "stari")
        self.assertEqual(ntl["datum"], "2026-11-04")
        self.assertIn("ntl", self.pr["l"])

    def test_interspar_odvojen(self):
        self.assertIn("interspar", self.pr["l"])
        self.assertTrue(any(p[0] == "interspar" for p in self.pos["p"]))

    def test_grupe(self):
        self.assertEqual(self.grupa("3850104000011"), ("kruh", "bijeli"))
        self.assertEqual(self.grupa("3850104000035"), ("kruh", "sjemenke"))
        self.assertEqual(self.grupa("3850104000073")[0], "brasno")       # brašno za kruh nije kruh
        self.assertEqual(self.grupa("7622300000011")[0], "cokolada")     # mliječna čokolada nije mlijeko
        self.assertEqual(self.grupa("3850108000014"), ("mlijeko", "trajno"))
        self.assertEqual(self.grupa("3850108000038"), ("mlijeko", "bez-laktoze"))
        self.assertEqual(self.grupa("3850108000021"), ("mlijeko", "svjeze"))
        self.assertEqual(self.grupa("5411188000016")[0], "biljni-napitak")
        self.assertEqual(self.grupa("3850110000016")[0], "grickalice")   # čips paprika nije paprika
        self.assertEqual(self.grupa("3850111000013")[0], "sok")          # sok od jabuke nije jabuka
        self.assertEqual(self.grupa("3850109000017")[0], "jaja")
        self.assertEqual(self.grupa("2000000000015"), ("krumpir", "bijeli"))

    def test_poslovnice_i_datoteke(self):
        izlaz = self.t / "izlaz"
        for p in self.pos["p"]:
            d = json.loads((izlaz / "s" / f"{p[7]}.json").read_text())
            self.assertTrue("o" in d or "u" in d)
            self.assertEqual(len(d["d"]), len(d["c"]))
        # Tommy poslovnica s cijenom 0,00 za rižu nema rižu
        tommy = [p for p in self.pos["p"] if p[0] == "tommy"]
        self.assertEqual(len(tommy), 3)

    def test_koordinate(self):
        meta = json.loads((self.t / "izlaz2/meta.json").read_text())
        ktc = next(l for l in meta["lanci"] if l["id"] == "ktc")
        self.assertEqual((ktc["poslovnica"], ktc["s_koordinatama"]), (2, 1))

    def test_zastita_objave(self):
        t = self.t
        (t / "veliko.json").write_text(json.dumps({"proizvoda": 1000, "lanci": []}))
        rc = uvoz.main(["--arhiva", str(self.arhive[0]), "--izlaz", str(t / "izlaz3"), "--bez-dopune",
                        "--prethodni", str(t / "veliko.json"), "--izvjesce", str(t / "g.md"), "--privremeno", str(t / "tmp")])
        self.assertEqual(rc, 2)
        self.assertIn("Izvješće o grešci", (t / "g.md").read_text())
        self.assertIn("ZastitaObjave", (t / "g.md").read_text())


if __name__ == "__main__":
    unittest.main()
