"""Automatsko traženje uređaja: lokalna mreža, paralelno skeniranje, preskakanje poznatih, naredbe za instalatera."""
from __future__ import annotations

import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lokalno_vrijeme  # noqa: E402,F401  (zona simulirane lokacije)

from jezgra import konfig, otkrivanje  # noqa: E402
from jezgra.mqtt import Broker  # noqa: E402
from jezgra.simulacija import Lokacija, ProtokolniMost  # noqa: E402


class TestLokalnaMreza(unittest.TestCase):
    def test_samo_privatne_mreze_i_najvise_22(self):
        m = otkrivanje.lokalne_mreze(["192.168.1.0/24", "8.8.8.0/24", "10.0.0.0/8", "172.20.5.0/24"])
        self.assertIn("192.168.1.0/24", m)
        self.assertIn("172.20.5.0/24", m)
        self.assertNotIn("8.8.8.0/24", m)  # javna mreža se nikad ne skenira
        self.assertIn("10.0.0.0/22", m)    # preširoka mreža se sužava

    def test_vlastita_adresa_daje_24(self):
        with mock.patch.object(otkrivanje, "lokalne_adrese", return_value=["192.168.7.42"]):
            self.assertEqual(otkrivanje.lokalne_mreze(), ["192.168.7.0/24"])

    def test_nadji_otvorene_paralelno(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        try:
            t0 = time.monotonic()
            nadjeno = otkrivanje.nadji_otvorene(["127.0.0.0/29"], (port,), timeout=0.3)
            self.assertIn(("127.0.0.1", port), nadjeno)
            self.assertLess(time.monotonic() - t0, 2.0)
            self.assertEqual(otkrivanje.nadji_otvorene(["127.0.0.0/29"], (port,), preskoci={("127.0.0.1", port)}), [])
        finally:
            s.close()


class TestSkeniranje(unittest.TestCase):
    def setUp(self):
        cfg = konfig.ucitaj(Path(tempfile.mkdtemp()))
        self.broker = Broker().pokreni()
        self.lok = Lokacija(cfg, time.time())
        self.most = ProtokolniMost(self.lok, self.broker.port)
        self.most.osvjezi()

    def tearDown(self):
        self.most.zaustavi()
        self.broker.zaustavi()

    def test_paralelno_mrtvi_hostovi_ne_usporavaju(self):
        mrtvi = []
        for _ in range(6):  # zatvoreni portovi
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            mrtvi.append(("127.0.0.1", s.getsockname()[1]))
            s.close()
        t0 = time.monotonic()
        u = otkrivanje.skeniraj_modbus(mrtvi + [("127.0.0.1", self.most.modbus.port)], [1])
        self.assertEqual([x.protokol for x in u], ["modbus/sunspec"])
        self.assertLess(time.monotonic() - t0, 3.0)

    def test_poznati_se_preskacu(self):
        h = ("127.0.0.1", self.most.modbus.port)
        self.assertEqual(otkrivanje.skeniraj_modbus([h], [1], poznati={(h[0], h[1], 1)}), [])

    def test_registar_trazi_i_sazima(self):
        from jezgra.uredjaji import Registar

        class Jezgra:
            uredaji: list = []

            def _dogadjaj(self, *a, **k):
                pass

        j = Jezgra()
        r = Registar.__new__(Registar)
        r.j, r.cfg, r.hostovi = j, {"otkrivanje": {"modbus_jedinice": [1], "lan_skeniranje": False}}, \
            {("127.0.0.1", self.most.modbus.port)}
        import threading
        r._lock, r._zadnje_trazenje, r.zadnje_skeniranje = threading.Lock(), 0.0, {}
        s = r.skeniraj()
        self.assertEqual(len(s["novi_uredaji"]), 1)
        self.assertEqual(r.skeniraj()["novi_uredaji"], [])  # drugi put: već poznat, ne ispituje se ponovno


class TestApi(unittest.TestCase):
    def test_ruta_otkrivanja(self):
        from jezgra import api_v1

        class J:
            uredaji: list = []
        self.assertEqual(api_v1.obradi(J(), "stanar", "POST", "/api/v1/otkrivanje", {}, {})[0], 403)
        self.assertEqual(api_v1.obradi(J(), "administrator", "POST", "/api/v1/otkrivanje", {}, {})[0], 409)
        self.assertIn("/api/v1/otkrivanje", api_v1.openapi()["paths"])


class TestNaredbe(unittest.TestCase):
    def test_dijagnoza(self):
        from jezgra.__main__ import main
        with tempfile.TemporaryDirectory() as d, mock.patch("builtins.print") as p:
            kod = main(["--dijagnoza", "--podaci", d, "--port", "0"])
        ispis = "\n".join(str(c.args[0]) for c in p.call_args_list)
        self.assertIn("paket cryptography", ispis)
        self.assertIn(kod, (0, 1))


if __name__ == "__main__":
    unittest.main()
