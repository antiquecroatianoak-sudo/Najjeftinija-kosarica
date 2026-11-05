"""Koordinate poslovnica preko OpenStreetMap Nominatima (lažni poslužitelj, bez interneta)."""
import sys
import unittest
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "uvoz"))
from lokacije import (Lokacije, bez_kucnog_broja, kljuc, kljucna_rijec, ocisti_adresu, prihvati,  # noqa: E402
                      prihvati_trgovinu, prihvati_ulicu)

DANAS = date(2026, 11, 5)


def rez(lat, lon, rang, kat="building", vrsta="yes", drzava="hr", ime="", ulica=""):
    return {"lat": str(lat), "lon": str(lon), "place_rank": rang, "category": kat, "type": vrsta, "name": ime,
            "address": {"country_code": drzava, "road": ulica}}


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
        self.assertEqual(len(lazni.upiti), 3)                   # točna adresa, ulica bez broja, pa slobodni tekst
        self.assertEqual(lazni.upiti[0]["street"], "Ulica Svetog Nikole 16A")
        self.assertEqual(lazni.upiti[1]["street"], "Ulica Svetog Nikole")
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
        self.assertEqual(len(lazni3.upiti), 3)

    def test_ogranicenje_upita_odgada_ostatak(self):
        L, lazni = lok({}, najvise=8)                          # do 4 upita po adresi: stanu dvije adrese
        for i in range(5):
            L.trazi(f"Ulica {i}", "Grad")
        self.assertEqual(len(lazni.upiti), 6)
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

    def test_kucni_broj_i_kljucna_rijec(self):
        self.assertEqual(bez_kucnog_broja("K.TOMISLAVA 18 A"), "K. TOMISLAVA")
        self.assertEqual(bez_kucnog_broja("Marijana Celjaka bb"), "Marijana Celjaka")
        self.assertEqual(bez_kucnog_broja("Calinec 179_b"), "Calinec")
        self.assertEqual(kljucna_rijec("G.Lederera 27"), "lederera")
        self.assertEqual(kljucna_rijec("Marijana Celjaka bb"), "celjaka")
        self.assertEqual(kljucna_rijec("Zagrebačka cesta 70 C"), "zagrebacka")

    def test_trgovina_lanca_samo_u_istoj_ulici(self):
        dobra = rez(45.23, 16.54, 30, "shop", "convenience", ime="Gavranović", ulica="Ulica Gordana Lederera")
        self.assertEqual(prihvati_trgovinu(dobra, "Gavranović", "G.Lederera 27"), "trgovina")
        # Slatina: četiri različite NTL adrese, OSM vraća istu NTL trgovinu na D69 -> odbij
        druga = rez(45.70, 17.70, 30, "shop", "supermarket", ime="NTL", ulica="D69")
        self.assertIsNone(prihvati_trgovinu(druga, "NTL", "M.GUPCA 59"))
        # drugi lanac u istoj ulici nije ta poslovnica
        tudja = rez(45.23, 16.54, 30, "shop", "supermarket", ime="Konzum", ulica="Ulica Gordana Lederera")
        self.assertIsNone(prihvati_trgovinu(tudja, "Gavranović", "G.Lederera 27"))

    def test_ulica_bez_broja_ne_prihvaca_zgradu(self):
        benzinska = rez(45.55, 18.69, 30, "amenity", "fuel", ime="Petrol - Osijek Divaltova")
        self.assertIsNone(prihvati_ulicu(benzinska))
        self.assertEqual(prihvati_ulicu(rez(45.6, 18.2, 26, "highway", "residential")), "ulica")
        self.assertIsNone(prihvati_ulicu(rez(45.6, 18.2, 26, "highway", "secondary")))

    def test_trgovina_lanca_pronadena(self):
        L, lazni = lok({"Gavranović, Hrvatska Kostajnica": [
            rez(45.1, 16.4, 30, "shop", "supermarket", ime="NTL", ulica="Ulica Gordana Lederera"),
            rez(45.23, 16.54, 30, "shop", "convenience", ime="Gavranović", ulica="Ulica Gordana Lederera")]})
        self.assertEqual(L.trazi("G.Lederera 27", "Hrvatska Kostajnica", lanac="Gavranović"), (45.23, 16.54))
        self.assertEqual(L.stat["novo_trgovina"], 1)
        self.assertEqual(lazni.upiti[1]["limit"], "10")

    def test_stari_neuspjesi_traze_se_odmah_novim_nacinom(self):
        stara = {"a": {kljuc("Majstorska 9", "Zagreb"): [None, None, "", "2026-11-05"],
                       kljuc("Primorska 5", "Karlovac"): [45.49, 15.53, "adresa", "2026-11-05"]}}
        L, lazni = lok({"Majstorska 9": [rez(45.7861, 16.03037, 30)]}, stara)
        self.assertEqual(L.trazi("Majstorska 9", "Zagreb"), (45.7861, 16.03037))
        self.assertEqual(L.trazi("Primorska 5", "Karlovac"), (45.49, 15.53))
        self.assertEqual(len(lazni.upiti), 1)
        self.assertEqual(L.za_objavu()["pretraga"], 2)


if __name__ == "__main__":
    unittest.main()
