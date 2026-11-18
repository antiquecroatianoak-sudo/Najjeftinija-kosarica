"""Ulazi i izlazi na granicama sustava: postavke, očitanja uređaja, API, SunSpec oznake „nije dostupno”."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lokalno_vrijeme  # noqa: E402,F401

from jezgra import konfig  # noqa: E402
from jezgra.ulazi import broj, ocisti  # noqa: E402


class TestPostavke(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_tipfeler_tip_i_raspon(self):
        ok, upoz = konfig.provjeri({"baterija": {"kapacitet_kw": 10, "soc_max": "0.9", "max_punjenje_kw": 500,
                                                 "kapacitet_kwh": 12}})
        self.assertEqual(ok, {"baterija": {"kapacitet_kwh": 12}})
        tekst = "\n".join(upoz)
        self.assertIn("misli se na 'kapacitet_kwh'", tekst)
        self.assertIn("očekivano broj", tekst)
        self.assertIn("izvan raspona", tekst)

    def test_neispravno_ne_rusi_jezgru_i_vidi_se(self):
        (self.d / "postavke.json").write_text(json.dumps({"baterija": {"soc_min": 0.5, "soc_max": 0.4},
                                                          "mreza": {"dostupna": "da"}}))
        cfg = konfig.ucitaj(self.d)
        self.assertEqual((cfg["baterija"]["soc_min"], cfg["baterija"]["soc_max"]), (0.15, 0.9))
        self.assertIs(cfg["mreza"]["dostupna"], True)
        self.assertEqual(len(cfg["_upozorenja_postavki"]), 2)

    def test_legionela_ne_moze_ispod_60(self):
        ok, upoz = konfig.provjeri({"spremnik": {"legionela": {"cilj_c": 55}}})
        self.assertEqual(ok, {})
        self.assertTrue(upoz)

    def test_sadrzaj_popisa(self):
        ok, upoz = konfig.provjeri({"otkrivanje": {"modbus_hostovi": ["10.0.0.5"], "lan_mreze": ["abc"]}})
        self.assertEqual(ok, {})
        self.assertEqual(len(upoz), 2)
        ok, upoz = konfig.provjeri({"otkrivanje": {"modbus_hostovi": [["10.0.0.5", 502]]}})
        self.assertEqual((ok, upoz), ({"otkrivanje": {"modbus_hostovi": [["10.0.0.5", 502]]}}, []))

    def test_postavi_s_naredbenog_retka(self):
        nove, upoz = konfig.postavi(self.d, ["lokacija=45.33,14.44", "baterija.kapacitet_kwh=12,5",
                                             "mreza.dostupna=ne", "kapacitet=3"])
        self.assertEqual(nove, {"lokacija": {"sirina": 45.33, "duzina": 14.44}, "baterija": {"kapacitet_kwh": 12.5},
                                "mreza": {"dostupna": False}})
        self.assertEqual(len(upoz), 1)  # samo nepoznati ključ
        cfg = konfig.ucitaj(self.d)
        self.assertEqual(cfg["baterija"]["kapacitet_kwh"], 12.5)
        self.assertIn("baterija.kapacitet_kwh", cfg["_korisnicki_kljucevi"])
        self.assertNotIn("_upozorenja_postavki", cfg)

    def test_nedosljedan_skup_se_ne_upisuje(self):
        konfig.postavi(self.d, ["baterija.kapacitet_kwh=8"])
        nove, upoz = konfig.postavi(self.d, ["baterija.soc_min=0.5", "baterija.soc_max=0.4"])
        self.assertEqual(nove, {"baterija": {"kapacitet_kwh": 8}})
        self.assertTrue(any("soc_min < soc_max" in u for u in upoz))

    def test_naredbeni_redak(self):
        from jezgra.__main__ import main
        with mock.patch("builtins.print") as p:
            self.assertEqual(main(["--podaci", str(self.d), "--postavi", "fotonapon.kwp=6.5"]), 0)
            self.assertEqual(main(["--podaci", str(self.d), "--postavi", "fotonapon.kwp=-1"]), 1)
            self.assertEqual(main(["--podaci", str(self.d), "--postavke"]), 0)
        ispis = "\n".join(str(c.args[0]) for c in p.call_args_list if c.args)
        self.assertIn("fotonapon.kwp = 6.5", ispis)
        self.assertIn("izvan raspona", ispis)


class TestOcitanja(unittest.TestCase):
    def test_nemoguce_vrijednosti_se_odbacuju(self):
        cisto, odb = ocisti({"baterija_soc": 65.53, "pv_snaga_w": -32768.0, "tlo_z1_vlaga": float("nan"),
                             "baterija_temp_c": 58.0, "pastir_v2_kv": 0.0, "brojilo_impulsi": 123456,
                             "okolina_temp_c": float("inf"), "potrosnja_w": "x"})
        self.assertEqual(set(cisto), {"baterija_temp_c", "pastir_v2_kv", "brojilo_impulsi"})  # stvarne anomalije ostaju
        self.assertEqual(set(odb), {"baterija_soc", "pv_snaga_w", "tlo_z1_vlaga", "okolina_temp_c", "potrosnja_w"})

    def test_jezgra_ne_vidi_nan_i_javlja_ga(self):
        import copy
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        from jezgra.otkrivanje import Uredaj

        class Senzor(Uredaj):
            id, tip, protokol = "senzor-test", "senzor", "mqtt"

            def __init__(self):
                self.v = {"tlo_z1_vlaga": float("nan"), "baterija_soc": 0.5}

            def citaj(self):
                return dict(self.v)

        s = Senzor()
        with tempfile.TemporaryDirectory() as d:
            j = Jezgra(Path(d), copy.deepcopy(konfig.ZADANO), sat=SimSat(1.8e9), uredaji=[s])
            o = j._ocitaj()
            self.assertNotIn("tlo_z1_vlaga", o)
            self.assertIn("tlo_z1_vlaga", j.odbacena_ocitanja)
            s.v["tlo_z1_vlaga"] = 30.0
            self.assertEqual(j._ocitaj()["tlo_z1_vlaga"], 30.0)
            self.assertEqual(j.odbacena_ocitanja, {})
            j.zatvori()

    def test_sunspec_nije_dostupno(self):
        from jezgra.otkrivanje import SunSpecUredaj
        v = SunSpecUredaj.vrijednost
        self.assertIsNone(v(0xFFFF, 0xFFFF, False))     # SoC: uint16 nije dostupno
        self.assertIsNone(v(0x8000, 0, True))           # snaga: int16 nije dostupno
        self.assertIsNone(v(500, 0x8000, False))        # faktor skale nije dostupan
        self.assertAlmostEqual(v(562, 0xFFFF, False), 56.2)
        self.assertEqual(v(0xFF9C, 0, True), -100)


class TestNazivno(unittest.TestCase):
    def test_samo_ako_instalater_nije_upisao(self):
        import copy
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        with tempfile.TemporaryDirectory() as d:
            cfg = copy.deepcopy(konfig.ZADANO)
            cfg["_korisnicki_kljucevi"] = ["baterija.max_praznjenje_kw"]
            j = Jezgra(Path(d), cfg, sat=SimSat(1.8e9))
            j.primijeni_nazivno("sunspec-x", {"baterija_max_kw": 2.5})
            self.assertEqual(j.cfg["baterija"]["max_punjenje_kw"], 2.5)
            self.assertEqual(j.cfg["baterija"]["max_praznjenje_kw"], 3.0)  # upisao instalater: ostaje
            self.assertEqual(j.nazivni_podaci, {"sunspec-x": {"max_punjenje_kw": 2.5}})
            j.zatvori()


class TestApiUlazi(unittest.TestCase):
    def test_broj(self):
        self.assertEqual(broj(["7"], "dana", 1, 366), 7.0)
        self.assertEqual(broj("2,5", "x", 0, 10), 2.5)
        for los in ("abc", float("nan"), float("inf"), True, None, 400):
            with self.assertRaises(ValueError):
                broj(los, "dana", 1, 366)

    def test_400_umjesto_500(self):
        import copy
        from jezgra import api_v1
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        with tempfile.TemporaryDirectory() as d:
            j = Jezgra(Path(d), copy.deepcopy(konfig.ZADANO), sat=SimSat(1.8e9))
            o = api_v1.obradi
            self.assertEqual(o(j, "administrator", "GET", "/api/v1/izvjestaj", {"dana": ["abc"]}, None)[0], 400)
            self.assertEqual(o(j, "administrator", "GET", "/api/v1/povijest", {"korak": ["0"]}, None)[0], 400)
            self.assertEqual(o(j, "administrator", "GET", "/api/v1/usteda", {"dana": ["x"]}, None)[0], 400)
            self.assertEqual(o(j, "administrator", "GET", "/api/v1/dogadjaji", {"sati": ["nan"]}, None)[0], 400)
            self.assertEqual(o(j, "administrator", "POST", "/api/v1/naredbe", {}, ["lista"])[0], 400)
            self.assertEqual(o(j, "administrator", "POST", "/api/v1/naredbe", {},
                               {"akcija": "trosilo", "trosilo": "bojler", "minuta": "pola sata"})[0], 400)
            s, _ = o(j, "administrator", "POST", "/api/v1/naredbe", {},
                     {"akcija": "trosilo", "trosilo": "bojler", "ukljuci": "false"})
            self.assertEqual(s, 400)
            self.assertNotIn("bojler", j.rucno)
            # NaN snaga u ručnom načinu više ne znači punu snagu punjenja
            s, r = o(j, "administrator", "POST", "/api/v1/postavke", {},
                     {"baterija_nacin": "rucno", "rucna_snaga_w": float("nan")})
            self.assertEqual(s, 400)
            self.assertNotEqual(j.napredno.get("rucna_snaga_w"), 3000.0)
            s, r = o(j, "operator" if "operator" in api_v1.ULOGE else "administrator", "POST",
                     "/api/v1/mreza/zahtjevi", {}, {"vrsta": "ogranici_uvoz", "snaga_w": "puno"})
            self.assertEqual(s, 400)
            from jezgra import api
            self.assertEqual(api.obradi(j, "GET", "/api/izvjestaj", {"dana": ["-5"]}, None)[0], 400)
            self.assertEqual(api.obradi(j, "POST", "/api/naredba", {}, "tekst")[0], 400)
            self.assertFalse(math.isnan(j.napredno.get("rucna_snaga_w", 0.0)))
            j.zatvori()


class TestReferenca(unittest.TestCase):
    def test_dokument_nije_zastario(self):
        from jezgra import referenca
        d = referenca.DOKUMENT.read_text("utf-8")
        generirano = d[d.index(referenca.POCETAK) + len(referenca.POCETAK):d.index(referenca.KRAJ)].strip()
        self.assertEqual(generirano, referenca.generiraj().strip(),
                         "ULAZI_IZLAZI.md zaostaje za kodom: python3 -m jezgra.referenca --upisi")


if __name__ == "__main__":
    unittest.main()
