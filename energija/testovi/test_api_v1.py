"""API v1 preko pravog HTTP poslužitelja: uloge, pozivnice, SSE, OpenAPI, CORS, povijest, zahtjevi mreže."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jezgra import konfig  # noqa: E402
from jezgra.api import pokreni_api  # noqa: E402
from jezgra.jezgra import Jezgra  # noqa: E402
from jezgra.simulacija import Lokacija, izravni_uredaji  # noqa: E402


class Sat:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class TestApiV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        cfg = copy.deepcopy(konfig.ZADANO)
        cfg["api"]["cors_izvori"] = ["https://portal.primjer"]
        t0 = time.mktime((2026, 6, 5, 6, 0, 0, 0, 0, -1))
        cls.lok = Lokacija(cfg, t0, kvarovi=False)
        cls.sat = Sat(t0)
        cls.j = Jezgra(Path(cls._d.name), cfg, sat=cls.sat, uredaji=izravni_uredaji(cls.lok),
                       dohvati_prognozu=cls.lok.prognoza_api)
        for _ in range(180):
            cls.lok.korak(60)
            cls.sat.t = cls.lok.t
            cls.j.korak()
        cls.srv, adresa = pokreni_api(cls.j, 0, tls=False, host="127.0.0.1")
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.admin = cls.zahtjev("POST", "/api/v1/upari", {"kod": cls.j.pristup.kod, "ime": "test"})[1]["token"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.j.zatvori()
        cls._d.cleanup()

    @classmethod
    def zahtjev(cls, metoda, put, tijelo=None, token=None, zaglavlja=None):
        z = urllib.request.Request(cls.url + put, method=metoda, data=None if tijelo is None else json.dumps(tijelo).encode(),
                                   headers={"Content-Type": "application/json", **(zaglavlja or {}),
                                            **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(z, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), dict(e.headers)

    def test_uloge_i_pozivnice(self):
        s, v, _ = self.zahtjev("GET", "/api/v1/sustav", token=self.admin)
        self.assertEqual((s, v["uloga"]), (200, "administrator"))
        self.assertEqual(self.zahtjev("GET", "/api/v1/pregled")[0], 401)
        s, p, _ = self.zahtjev("POST", "/api/v1/pristup/pozivnice", {"uloga": "stanar"}, token=self.admin)
        self.assertEqual(s, 200)
        s, v, _ = self.zahtjev("POST", "/api/v1/upari", {"kod": p["kod"], "ime": "mobitel"})
        stanar = v["token"]
        self.assertEqual(v["uloga"], "stanar")
        self.assertEqual(self.zahtjev("POST", "/api/v1/upari", {"kod": p["kod"]})[0], 403)  # jednokratan
        self.assertEqual(self.zahtjev("GET", "/api/v1/pregled", token=stanar)[0], 200)
        self.assertEqual(self.zahtjev("GET", "/api/v1/dijagnostika", token=stanar)[0], 403)
        self.assertEqual(self.zahtjev("POST", "/api/v1/postavke", {"ai": False}, token=stanar)[0], 403)
        self.assertEqual(self.zahtjev("POST", "/api/v1/pristup/pozivnice", {"uloga": "administrator"}, token=stanar)[0], 403)
        s, v, _ = self.zahtjev("POST", "/api/v1/naredbe", {"akcija": "topla_voda_sada"}, token=stanar)
        self.assertEqual(s, 200)
        self.assertIn("bojler", self.j.rucno)
        self.assertEqual(self.zahtjev("POST", "/api/v1/naredbe", {"akcija": "trosilo", "trosilo": "bojler"},
                                      token=stanar)[0], 403)
        self.assertEqual(self.zahtjev("GET", "/api/stanje", token=stanar)[0], 401)  # stari API samo administrator

    def test_resursi_i_povijest(self):
        for put in ("/api/v1/pregled", "/api/v1/tok", "/api/v1/bojler", "/api/v1/solar", "/api/v1/baterija",
                    "/api/v1/pastir", "/api/v1/navodnjavanje", "/api/v1/odluke", "/api/v1/dijagnostika",
                    "/api/v1/usteda", "/api/v1/fleksibilnost", "/api/v1/dogadjaji"):
            s, v, _ = self.zahtjev("GET", put, token=self.admin)
            self.assertEqual(s, 200, (put, v))
        s, v, _ = self.zahtjev("GET", "/api/v1/povijest?serije=pv_w,potrosnja_w,pastir_v1_kv,tlo_z1_vlaga&raspon=6h",
                               token=self.admin)
        self.assertEqual(s, 200)
        self.assertEqual(len(v["t"]), len(v["serije"]["pv_w"]))
        self.assertTrue(any(x is not None for x in v["serije"]["pastir_v1_kv"]))
        self.assertEqual(self.zahtjev("GET", "/api/v1/povijest?serije=lozinka", token=self.admin)[0], 400)
        self.assertEqual(self.zahtjev("GET", "/api/v1/nepostoji", token=self.admin)[0], 404)
        self.assertEqual(self.zahtjev("DELETE", "/api/v1/pregled", token=self.admin)[0], 405)

    def test_openapi_pokriva_sve_rute(self):
        from jezgra.api_v1 import RUTE
        s, spec, _ = self.zahtjev("GET", "/api/v1/openapi.json")
        self.assertEqual((s, spec["openapi"]), (200, "3.1.0"))
        for metoda, put, *_ in RUTE:
            self.assertIn(metoda.lower(), spec["paths"][put])

    def test_cors_samo_za_dopustene(self):
        _, _, h = self.zahtjev("GET", "/api/v1/tok", token=self.admin, zaglavlja={"Origin": "https://portal.primjer"})
        self.assertEqual(h.get("Access-Control-Allow-Origin"), "https://portal.primjer")
        _, _, h = self.zahtjev("GET", "/api/v1/tok", token=self.admin, zaglavlja={"Origin": "https://zlo.primjer"})
        self.assertNotIn("Access-Control-Allow-Origin", h)

    def test_zahtjev_mreze(self):
        s, z, _ = self.zahtjev("POST", "/api/v1/mreza/zahtjevi", {"vrsta": "ogranici_uvoz", "snaga_w": 500,
                                                                   "do": self.sat.t + 1800, "izvor": "DSO"}, token=self.admin)
        self.assertEqual(s, 200)
        self.assertEqual(self.zahtjev("GET", "/api/v1/mreza/zahtjevi", token=self.admin)[1]["zahtjevi"][-1]["id"], z["id"])
        self.assertEqual(self.zahtjev("POST", "/api/v1/mreza/zahtjevi", {"vrsta": "x"}, token=self.admin)[0], 400)
        self.assertEqual(self.zahtjev("DELETE", f"/api/v1/mreza/zahtjevi?id={z['id']}", token=self.admin)[0], 200)

    def test_uzivo_sse(self):
        z = urllib.request.Request(f"{self.url}/api/v1/uzivo?token={self.admin}")
        with urllib.request.urlopen(z, timeout=10) as r:
            self.assertTrue(r.headers["Content-Type"].startswith("text/event-stream"))
            redovi = []
            while len(redovi) < 3:
                l = r.readline().decode().strip()
                if l:
                    redovi.append(l)
        self.assertEqual(redovi[1], "event: stanje")
        self.assertIn("tok", json.loads(redovi[2][6:]))


if __name__ == "__main__":
    unittest.main()
