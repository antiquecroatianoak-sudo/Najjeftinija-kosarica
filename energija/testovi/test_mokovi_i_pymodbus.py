"""Mokovi mrežnih poziva prema Open-Meteo i interoperabilnost s pymodbus simulatorom.

    python3 -m unittest discover -s testovi -p "test_*.py"   (iz mape energija/)
"""
from __future__ import annotations

import copy
import io
import json
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jezgra import konfig  # noqa: E402
from jezgra.prognoza import Prognoza  # noqa: E402

SADA = 1_783_000_000.0  # fiksno vrijeme (srpanj 2026., podne UTC ±)


def odgovor_openmeteo(pocetak: float, sati: int = 48, zracenje: float = 600.0, kisa: float = 0.0) -> dict:
    t = [int(pocetak - pocetak % 3600 + i * 3600) for i in range(sati)]
    return {"latitude": 45.81, "longitude": 15.98, "hourly_units": {"shortwave_radiation": "W/m²"},
            "hourly": {"time": t, "shortwave_radiation": [zracenje] * sati, "temperature_2m": [20.0] * sati,
                       "precipitation": [kisa] * sati, "cloud_cover": [10] * sati}}


def lazni_urlopen(tijelo: bytes | None = None, iznimka: Exception | None = None):
    """Mok za urllib.request.urlopen koji pamti URL-ove i vraća zadani odgovor (context manager)."""
    pozivi: list[str] = []

    def urlopen(url, timeout=None, **_):
        pozivi.append(url if isinstance(url, str) else url.full_url)
        if iznimka:
            raise iznimka
        r = io.BytesIO(tijelo)
        r.status = 200
        return r

    return mock.MagicMock(side_effect=urlopen), pozivi


class TestOpenMeteoMokovi(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)
        self.cfg = copy.deepcopy(konfig.ZADANO)

    def tearDown(self):
        self._d.cleanup()

    def test_uspjeh_ispravan_upit_i_parsiranje(self):
        m, pozivi = lazni_urlopen(json.dumps(odgovor_openmeteo(SADA)).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            self.assertTrue(p.osvjezi(SADA))
        self.assertEqual(len(pozivi), 1)
        u = urllib.parse.urlparse(pozivi[0])
        q = urllib.parse.parse_qs(u.query)
        self.assertEqual(f"{u.scheme}://{u.netloc}{u.path}", "https://api.open-meteo.com/v1/forecast")
        self.assertEqual(q["latitude"], ["45.81"])
        self.assertEqual(q["longitude"], ["15.98"])
        self.assertEqual(q["timeformat"], ["unixtime"])
        self.assertEqual(set(q["hourly"][0].split(",")),
                         {"shortwave_radiation", "temperature_2m", "precipitation", "cloud_cover"})
        niz = p.niz(SADA, 24)
        self.assertTrue(all(s["izvor"] == "prognoza" for s in niz))
        self.assertGreater(niz[0]["pv_w"], 1500)  # 600 W/m² na 5 kWp
        self.assertTrue((self.d / "prognoza.json").exists())  # predmemorija za rad bez mreže
        self.assertIsNone(p.greska)

    def test_url_iz_postavki(self):
        self.cfg["prognoza"]["url"] = "http://mock-openmeteo:8080/v1/forecast"
        m, pozivi = lazni_urlopen(json.dumps(odgovor_openmeteo(SADA)).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            Prognoza(self.cfg, self.d).osvjezi(SADA)
        self.assertTrue(pozivi[0].startswith("http://mock-openmeteo:8080/v1/forecast?"))

    def test_pad_mreze_zamjenski_model(self):
        m, _ = lazni_urlopen(iznimka=urllib.error.URLError("nema mreže"))
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            self.assertFalse(p.osvjezi(SADA))
        self.assertIn("URLError", p.greska)
        niz = p.niz(SADA, 48)
        self.assertTrue(all(s["izvor"] == "procjena" for s in niz))
        self.assertTrue(any(s["pv_w"] > 0 for s in niz))  # model vedrog neba radi i bez interneta
        self.assertIsNone(p.kisa_sljedecih(SADA))  # kiša se ne izmišlja

    def test_istek_vremena(self):
        m, _ = lazni_urlopen(iznimka=socket.timeout("timed out"))
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            self.assertFalse(p.osvjezi(SADA))
        self.assertTrue(p.greska)

    def test_http_greska_servisa(self):
        greska = urllib.error.HTTPError("https://api.open-meteo.com", 429, "Too Many Requests", {}, io.BytesIO(b""))
        m, _ = lazni_urlopen(iznimka=greska)
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            self.assertFalse(p.osvjezi(SADA))
        self.assertIn("429", p.greska)

    def test_neispravan_odgovor_cuva_staru_prognozu(self):
        dobar, _ = lazni_urlopen(json.dumps(odgovor_openmeteo(SADA, kisa=2.0)).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", dobar):
            p = Prognoza(self.cfg, self.d)
            p.osvjezi(SADA)
        for lose in (b"<html>gateway</html>", json.dumps({"hourly": {"time": [1]}}).encode()):
            m, _ = lazni_urlopen(lose)
            with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
                self.assertFalse(p.osvjezi(SADA + 4 * 3600))
            self.assertEqual(p.niz(SADA + 4 * 3600, 1)[0]["izvor"], "prognoza")  # stara još pokriva
        self.assertAlmostEqual(p.kisa_sljedecih(SADA + 4 * 3600, 12), 24.0)

    def test_null_vrijednosti_u_nizovima(self):
        v = odgovor_openmeteo(SADA, sati=3)
        v["hourly"]["shortwave_radiation"][1] = None
        v["hourly"]["temperature_2m"][2] = None
        m, _ = lazni_urlopen(json.dumps(v).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            self.assertTrue(p.osvjezi(SADA))
        self.assertEqual(p.niz(SADA, 3)[1]["pv_w"], 0.0)

    def test_predmemorija_bez_ponovnog_poziva_i_ucitavanje_offline(self):
        m, pozivi = lazni_urlopen(json.dumps(odgovor_openmeteo(SADA)).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            p = Prognoza(self.cfg, self.d)
            p.osvjezi(SADA)
            p.osvjezi(SADA + 3600)  # unutar 3 h: bez novog poziva (štedi bateriju i podatke)
            self.assertEqual(len(pozivi), 1)
            p.osvjezi(SADA + 4 * 3600)
            self.assertEqual(len(pozivi), 2)
        zabranjeno = mock.MagicMock(side_effect=AssertionError("ne smije zvati mrežu"))
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", zabranjeno):
            p2 = Prognoza(self.cfg, self.d)  # novi proces nakon ponovnog pokretanja
            self.assertTrue(p2.osvjezi(SADA + 4 * 3600 + 60))
            self.assertEqual(p2.niz(SADA + 5 * 3600, 1)[0]["izvor"], "prognoza")

    def test_jezgra_s_mokom_kise_preskace_zalijevanje(self):
        """Cijeli tok: mokani Open-Meteo javlja kišu -> navodnjavanje se ne pokreće."""
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        from jezgra.simulacija import Lokacija, izravni_uredaji

        pocetak = time.mktime((2026, 6, 1, 6, 0, 0, 0, 0, -1))
        lok = Lokacija(self.cfg, pocetak, kvarovi=False)
        lok.vlaga = {"z1": 20.0, "z2": 20.0}  # suho
        sat = SimSat(pocetak)
        m, pozivi = lazni_urlopen(json.dumps(odgovor_openmeteo(pocetak, kisa=1.0)).encode())
        with mock.patch("jezgra.prognoza.urllib.request.urlopen", m):
            j = Jezgra(self.d, self.cfg, sat=sat, uredaji=izravni_uredaji(lok))
            for _ in range(5):
                lok.korak(60)
                sat.t = lok.t
                j.korak()
        self.assertGreaterEqual(len(pozivi), 1)
        self.assertFalse(lok.releji["pumpa"])
        self.assertIn("kiše", j.navodnjavanje_izlaz["razlog"])
        self.assertEqual(j.stanje()["prognoza"]["izvor"], "prognoza")
        j.zatvori()


try:
    import pymodbus  # noqa: F401
    IMA_PYMODBUS = True
except ImportError:
    IMA_PYMODBUS = False


def slobodan_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@unittest.skipUnless(IMA_PYMODBUS, "pymodbus nije instaliran (pip install -r requirements-provjera.txt)")
class TestPymodbusInterop(unittest.TestCase):
    """Klijent jezgre (vlastita implementacija) prema neovisnoj implementaciji poslužitelja (pymodbus)."""

    @classmethod
    def setUpClass(cls):
        from simulator.modbus_pymodbus import Farma, u_niti
        cls.farma = Farma(brzina=60, kvarovi=False)
        cls.port = slobodan_port()
        u_niti(cls.farma, cls.port)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    def test_otkrivanje_sunspec_i_sdm(self):
        from jezgra.otkrivanje import SdmBrojilo, SunSpecUredaj, skeniraj_modbus
        uredaji = skeniraj_modbus([("127.0.0.1", self.port)], [1, 2, 3])
        tipovi = {type(u) for u in uredaji}
        self.assertEqual(tipovi, {SunSpecUredaj, SdmBrojilo})
        ss = next(u for u in uredaji if isinstance(u, SunSpecUredaj))
        self.assertEqual(ss.proizvodjac, "EnergijaSim-pymodbus")
        self.assertEqual(set(ss.modeli), {1, 103, 124})
        o = ss.citaj()
        self.assertAlmostEqual(o["baterija_soc"], self.farma.lok.soc, delta=0.01)
        self.assertGreater(o["baterija_napon_v"], 40)
        sdm = next(u for u in uredaji if isinstance(u, SdmBrojilo)).citaj()
        self.assertIn("mreza_snaga_w", sdm)
        self.assertAlmostEqual(sdm["mreza_snaga_w"], self.farma.lok.mreza_w, delta=300)

    def test_upravljanje_baterijom_preko_modbusa(self):
        from jezgra.otkrivanje import skeniraj_modbus, SunSpecUredaj
        ss = next(u for u in skeniraj_modbus([("127.0.0.1", self.port)], [1]) if isinstance(u, SunSpecUredaj))
        self.assertTrue(ss.postavi("baterija_snaga_w", 1500))
        self.assertAlmostEqual(self.farma.lok.naredba_bat, 1500, delta=31)  # 1 % koraka od 3000 W
        self.assertTrue(ss.postavi("baterija_snaga_w", -900))
        self.assertAlmostEqual(self.farma.lok.naredba_bat, -900, delta=31)
        self.assertTrue(ss.postavi("baterija_auto", 1))
        self.assertIsNone(self.farma.lok.naredba_bat)  # izmjenjivač u vlastitom načinu

    def test_nepostojeca_jedinica_i_registar(self):
        from jezgra.modbus import ModbusGreska, ModbusKlijent
        from jezgra.otkrivanje import probaj_sdm, probaj_sunspec
        k = ModbusKlijent("127.0.0.1", self.port, timeout=0.5, pokusaja=1)
        self.assertIsNone(probaj_sunspec(k, 2))  # brojilo nema SunSpec
        self.assertIsNone(probaj_sdm(k, 1))      # izmjenjivač nema SDM registre
        with self.assertRaises((ModbusGreska, ConnectionError)):
            k.citaj_holding(1, 60000, 2)

    def test_jezgra_koristi_pymodbus_uredaje(self):
        from jezgra.jezgra import Jezgra
        from jezgra.otkrivanje import skeniraj_modbus
        with tempfile.TemporaryDirectory() as d:
            cfg = copy.deepcopy(konfig.ZADANO)
            cfg["prognoza"]["url"] = "http://127.0.0.1:9/v1/forecast"  # zatvoren port: bez interneta
            j = Jezgra(Path(d), cfg, uredaji=skeniraj_modbus([("127.0.0.1", self.port)], [1, 2]))
            j.korak()
            s = j.stanje()
            self.assertEqual({u["protokol"] for u in s["uredaji"]}, {"modbus/sunspec", "modbus/sdm"})
            self.assertIsNotNone(s["energija"]["baterija_soc"])
            self.assertEqual(s["prognoza"]["izvor"], "procjena")  # mreža nedostupna -> zamjenski model
            self.assertIn("baterija", s["odluke"])
            j.zatvori()


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(IMA_PYMODBUS, "pymodbus nije instaliran")
class TestIspadStvarnogModbusa(unittest.TestCase):
    def test_ispad_i_oporavak_pymodbus_posluzitelja(self):
        """Pravi pymodbus poslužitelj se ugasi i ponovno upali: jezgra bilježi ispad, ne ruši se, sama se spaja."""
        from jezgra.jezgra import Jezgra
        from jezgra.otkrivanje import skeniraj_modbus
        from simulator.modbus_pymodbus import Farma, u_niti

        def cekaj_port(port, otvoren=True):
            for _ in range(60):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    if otvoren:
                        return True
                except OSError:
                    if not otvoren:
                        return True
                time.sleep(0.1)
            return False

        farma, port = Farma(brzina=60, kvarovi=False), slobodan_port()
        nit = u_niti(farma, port)
        self.assertTrue(cekaj_port(port))
        with tempfile.TemporaryDirectory() as d:
            cfg = copy.deepcopy(konfig.ZADANO)
            cfg["prognoza"]["url"] = "http://127.0.0.1:9/v1/forecast"
            j = Jezgra(Path(d), cfg, uredaji=skeniraj_modbus([("127.0.0.1", port)], [1, 2]))
            j.korak()
            self.assertFalse(j.offline_uredaji)
            nit.zaustavi()
            self.assertTrue(cekaj_port(port, otvoren=False))
            j.korak()  # uređaji ne odgovaraju
            self.assertEqual(len(j.offline_uredaji), 2)
            self.assertIn("baterija", j.odluke)  # jezgra i dalje odlučuje (bez rušenja)
            nit = u_niti(farma, port)
            self.assertTrue(cekaj_port(port))
            j.korak()  # klijent se sam ponovno spaja
            self.assertFalse(j.offline_uredaji)
            poruke = [z["d"]["poruka"] for z in j.arhiva.citaj(0, {"uredaj"})]
            self.assertEqual(sum("nedostupan" in p for p in poruke), 2)
            self.assertEqual(sum("ponovno dostupan" in p for p in poruke), 2)
            j.zatvori()
        nit.zaustavi()


class TestCuvarHvataKrsenja(unittest.TestCase):
    """Test testera: čuvar invarijanti mora prijaviti namjerno loše ponašanje."""

    def test_cuvar(self):
        from scenariji.pokretac import Cuvar
        from jezgra.simulacija import Lokacija
        cfg = copy.deepcopy(konfig.ZADANO)
        lok = Lokacija(cfg, SADA, kvarovi=False)
        c = Cuvar(cfg, 60)
        lok.soc, lok.naredba_bat = 0.10, -1500.0
        c.provjeri(lok)
        lok.soc, lok.naredba_bat, lok.bat_temp = 0.5, 800.0, -3.0
        c.provjeri(lok)
        lok.naredba_bat, lok.releji["pumpa"], lok.suho = None, True, True
        c.provjeri(lok)
        c.provjeri(lok)
        self.assertEqual([k["vrsta"] for k in c.krsenja], ["praznjenje_ispod_min", "punjenje_na_hladnom"])
        self.assertEqual(c.suho_max, 2)
        lok.pastir_sklopke[1] = False  # ograda odspojena bez kvara -> ispravne dionice bez napona
        for _ in range(40):
            c.provjeri(lok)
        self.assertGreater(c.bez_napona_max_min, 30)

    def test_kratki_scenarij_prolazi(self):
        from scenariji.katalog import po_imenu
        from scenariji.pokretac import pokreni
        import dataclasses
        sc = dataclasses.replace(po_imenu("visestruki_kvarovi_ograde"), dani=1.0, korak_s=120,
                                 ocekivanja={"izolacija_max_min": 20})  # skraćeno: samo prvi kvar
        r = pokreni(sc)
        self.assertTrue(r["prosao"], r["neuspjesi"])
        self.assertEqual(r["kpi"]["pastir_izolacija"], 1)
