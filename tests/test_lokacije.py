"""Koordinate poslovnica preko OpenStreetMap Nominatima (lažni poslužitelj, bez interneta)."""
import sys
import unittest
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "uvoz"))
from lokacije import Lokacije, kljuc, ocisti_adresu, prihvati  # noqa: E402

DANAS = date(2026, 11, 5)


def rez(lat, lon, rang, kat="building", vrsta="yes", drzava="hr"):
    return {"lat": str(lat), "lon": str(lon), "place_rank": rang, "category": kat, "type": vrsta,
            "address": {"country_code": drzava}}


class Lazni:
    """Odgovara prema ulici (strukturirani upit) ili tekstu (slobodni upit); bilježi upite."""

    def __init__(self, odgovori):
        self.odgovori, self.upiti = odgovori, []

    def __call__(self, url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        self.upiti.append(q)
        return self.odgovori.get(q.get("street") or q.get("q"), [])


def lok(odgovori, predmemorija=None, najvise=400):
    lazni = Lazni(odgovori)
    return Lokacije(predmemorija, "test", najvise=najvise, pauza=0, dohvati=lazni, danas=DANAS), lazni


class Lokacije_(unittest.TestCase):
    def test_ciscenje_adrese(self):
        self.assertEqual(ocisti_adresu("Ulica Svetog Nikole16A"), "Ulica Svetog Nikole 16A")
        self.assertEqual(ocisti_adresu("A.Senoe 14"), "A. Senoe 14")
        self.assertEqual(ocisti_adresu("  Soblinecka 55,  Soblinec "), "Soblinecka 55, Soblinec")
        self.assertEqual(kljuc("Braće Gojaka 4", "Karlovac"), kljuc("Brace  Gojaka 4", "KARLOVAC"))

    def test_kucni_broj_prihvacen(self):
        self.assertEqual(prihvati(rez(45.78, 16.03, 30)), "adresa")

    def test_lokalna_ulica_prihvacena_glavna_cesta_nije(self):
        self.assertEqual(prihvati(rez(46.15, 15.87, 26, "highway", "unclassified")), "ulica")
        # Cesta dr. Franje Tuđmana kroz Kaštela je duga kilometrima: bolje bez točke nego s pogrešnom
        self.assertIsNone(prihvati(rez(43.55, 16.39, 26, "highway", "secondary")))
        self.assertIsNone(prihvati(rez(45.86, 16.15, 26, "highway", "primary")))

    def test_grad_i_inozemstvo_odbijeni(self):
        self.assertIsNone(prihvati(rez(45.81, 15.98, 16, "boundary", "administrative")))
        self.assertIsNone(prihvati(rez(45.81, 15.98, 30, drzava="si")))
        self.assertIsNone(prihvati(rez(48.2, 16.37, 30)))

    def test_trazi_pa_slobodni_upit(self):
        L, lazni = lok({"Ulica Svetog Nikole 16A, Solin": [rez(43.54, 16.49, 30)]})
        self.assertEqual(L.trazi("Ulica Svetog Nikole16A", "Solin"), (43.54, 16.49))
        self.assertEqual(len(lazni.upiti), 2)                   # strukturirani bez rezultata, pa slobodni
        self.assertEqual(lazni.upiti[0]["street"], "Ulica Svetog Nikole 16A")
        self.assertEqual(lazni.upiti[0]["countrycodes"], "hr")
        self.assertEqual(L.stat["novo_adresa"], 1)

    def test_predmemorija_bez_ponovnog_upita(self):
        L, lazni = lok({"Majstorska 9": [rez(45.7861, 16.03037, 30)]})
        L.trazi("Majstorska 9", "Zagreb")
        L2, lazni2 = lok({}, L.za_objavu())
        self.assertEqual(L2.trazi("Majstorska 9", "Zagreb"), (45.7861, 16.03037))
        self.assertEqual(lazni2.upiti, [])

    def test_neuspjeh_se_pamti_pa_ponavlja_nakon_30_dana(self):
        L, _ = lok({})
        self.assertIsNone(L.trazi("Nepostojeca 1", "Nigdje"))
        zapis = L.za_objavu()
        L2, lazni2 = lok({}, zapis)
        self.assertIsNone(L2.trazi("Nepostojeca 1", "Nigdje"))
        self.assertEqual(lazni2.upiti, [])
        zapis["a"][kljuc("Nepostojeca 1", "Nigdje")][3] = "2026-09-01"
        L3, lazni3 = lok({}, zapis)
        L3.trazi("Nepostojeca 1", "Nigdje")
        self.assertEqual(len(lazni3.upiti), 2)

    def test_ogranicenje_upita_odgada_ostatak(self):
        L, lazni = lok({}, najvise=4)
        for i in range(5):
            L.trazi(f"Ulica {i}", "Grad")
        self.assertEqual(len(lazni.upiti), 4)
        self.assertEqual(L.stat["odgodeno"], 3)
        # odgođene adrese nisu zapisane kao neuspjele: idući dan se traže
        self.assertNotIn(kljuc("Ulica 4", "Grad"), L.za_objavu()["a"])

    def test_kvar_posluzitelja_prekida_bez_rusenja(self):
        def kvar(url):
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        L = Lokacije({}, "test", pauza=0, dohvati=kvar, danas=DANAS)
        self.assertIsNone(L.trazi("Majstorska 9", "Zagreb"))
        self.assertIsNone(L.trazi("Primorska 5", "Karlovac"))
        self.assertTrue(L.prekid)
        self.assertEqual(L.stat["greska"], 1)
        self.assertEqual(L.za_objavu()["a"], {})              # kvar se ne pamti kao "nije nađeno"


if __name__ == "__main__":
    unittest.main()
