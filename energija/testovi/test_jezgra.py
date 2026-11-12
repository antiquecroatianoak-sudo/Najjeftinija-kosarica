"""Testovi lokalne jezgre. Pokretanje iz mape energija/:
    python3 -m unittest discover -s testovi -p "test_*.py"
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jezgra import konfig  # noqa: E402
from jezgra.anomalije import Detektor, Trend  # noqa: E402
from jezgra.certifikati import LokalniCA  # noqa: E402
from jezgra.impulsi import DetektorImpulsa, ImpulsnoBrojilo  # noqa: E402
from jezgra.izvjestaji import potpisi, provjeri  # noqa: E402
from jezgra.kopije import Kopije  # noqa: E402
from jezgra.modbus import ModbusKlijent, ModbusPosluzitelj, Registri  # noqa: E402
from jezgra.mqtt import Broker, Klijent, odgovara  # noqa: E402
from jezgra.nadzor import Nadzornik  # noqa: E402
from jezgra.navodnjavanje import Navodnjavanje  # noqa: E402
from jezgra.optimizator import osnovni_scenarij, planiraj_bateriju, smjesti_fleksibilna  # noqa: E402
from jezgra.otkrivanje import iz_najave, probaj_sunspec  # noqa: E402
from jezgra.pastir import Pastir  # noqa: E402
from jezgra.pohrana import Dnevnik, Snimka  # noqa: E402
from jezgra.sifra import GreskaSifre, Sesija, Trezor, otpakiraj, zapakiraj  # noqa: E402
from jezgra.sinkronizacija import Sinkronizacija  # noqa: E402
from jezgra.tunel import Relej, TunelJezgre, TunelKlijent  # noqa: E402
from jezgra.ucenje import Navike  # noqa: E402


def cfg():
    return copy.deepcopy(konfig.ZADANO)


class Privremeno(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()


# ---------------------------------------------------------------- enkripcija
class TestSifra(Privremeno):
    def test_omotnica_i_izmjena(self):
        t = Trezor(self.d)
        k = t.kljuc("x")
        o = zapakiraj(k, b"tajna", b"aad")
        self.assertEqual(otpakiraj(k, o, b"aad"), b"tajna")
        with self.assertRaises(GreskaSifre):
            otpakiraj(k, o[:-1] + bytes([o[-1] ^ 1]), b"aad")
        with self.assertRaises(GreskaSifre):
            otpakiraj(k, o, b"drugi")
        self.assertEqual(Trezor(self.d).glavni, t.glavni)  # ključ je postojan
        self.assertEqual(os.stat(self.d / "kljucevi" / "glavni.key").st_mode & 0o777, 0o600)

    def test_dvosmjerna_sesija_i_odbijanje(self):
        tj, tk, tz = Trezor(self.d / "j"), Trezor(self.d / "k"), Trezor(self.d / "z")
        j, k = Sesija(tj, "jezgra"), Sesija(tk.potpisni, "klijent")
        pj, pk = j.pozdrav(), k.pozdrav()
        j.dovrsi(pk, {tk.javni_potpisni})
        k.dovrsi(pj, {tj.javni_potpisni})
        self.assertEqual(j.desifriraj(k.sifriraj(b"zahtjev")), b"zahtjev")
        p = j.sifriraj(b"odgovor")
        self.assertEqual(k.desifriraj(p), b"odgovor")
        with self.assertRaises(GreskaSifre):
            k.desifriraj(p)  # ponavljanje
        uljez = Sesija(tz.potpisni, "klijent")
        with self.assertRaises(GreskaSifre):
            Sesija(tj, "jezgra").dovrsi(uljez.pozdrav(), {tk.javni_potpisni})


class TestCertifikati(Privremeno):
    def test_tls_s_lokalnim_ca(self):
        t = Trezor(self.d)
        ca = LokalniCA(self.d, t)
        self.assertEqual(LokalniCA(self.d, t).otisak(), ca.otisak())  # učitan, ne nanovo stvoren
        srv_ctx = ca.kontekst_posluzitelja()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]

        def posluzi():
            c, _ = s.accept()
            with srv_ctx.wrap_socket(c, server_side=True) as x:
                x.sendall(b"ok")

        threading.Thread(target=posluzi, daemon=True).start()
        with ca.kontekst_klijenta().wrap_socket(socket.create_connection(("127.0.0.1", port)),
                                                server_hostname="localhost") as c:
            self.assertEqual(c.recv(2), b"ok")
        tudji = LokalniCA(self.d / "drugi", Trezor(self.d / "drugi"))
        s2 = socket.socket()
        s2.bind(("127.0.0.1", 0))
        s2.listen(1)
        p2 = s2.getsockname()[1]
        threading.Thread(target=lambda: srv_ctx.wrap_socket(s2.accept()[0], server_side=True), daemon=True).start()
        with self.assertRaises(ssl.SSLError):
            tudji.kontekst_klijenta().wrap_socket(socket.create_connection(("127.0.0.1", p2)), server_hostname="localhost")


# ---------------------------------------------------------------- pohrana i oporavak
class TestPohrana(Privremeno):
    def test_oporavak_odreze_osteceni_rep(self):
        k = os.urandom(32)
        d = Dnevnik(self.d, k)
        for i in range(10):
            d.zapisi("o", {"i": i}, kriticno=(i == 9))
        d.zatvori()
        seg = d.segmenti()[-1]
        with open(seg, "ab") as f:
            f.write(b"\x00\x00\x00\x00\x00\x00\x00\x0b\x00\x00\x00\x40nedovrseno")  # pad struje usred pisanja
        d2 = Dnevnik(self.d, k)
        self.assertGreater(d2.oporavak["odrezano_bajtova"], 0)
        self.assertEqual([z["d"]["i"] for z in d2.citaj()], list(range(10)))
        self.assertEqual(d2.zapisi("o", {"i": 10}), 11)
        self.assertEqual(len(list(d2.citaj(5))), 6)

    def test_snimka_koristi_prethodnu_kad_je_zadnja_ostecena(self):
        k = os.urandom(32)
        s = Snimka(self.d, k)
        s.spremi({"a": 1}, 5)
        s.spremi({"a": 2}, 9)
        s.p.write_bytes(b"E1" + os.urandom(40))
        st, slijed, izvor = s.ucitaj()
        self.assertEqual((st, slijed, izvor), ({"a": 1}, 5, "prethodna"))

    def test_kopije_provjera_obnova_i_podmetanje(self):
        k = os.urandom(32)
        podaci = self.d / "p"
        d = Dnevnik(podaci, k)
        for i in range(5):
            d.zapisi("o", {"i": i}, kriticno=True)
        Snimka(podaci, k).spremi({"x": 1}, 5)
        usb = self.d / "usb"
        usb.mkdir()
        kop = Kopije(podaci, k, [str(usb), str(self.d / "nema")])
        r = kop.napravi(d.segmenti())
        self.assertTrue(r[0]["ok"])
        self.assertFalse(r[1]["ok"])  # izvađen medij ne ruši ništa
        self.assertTrue(kop.provjeri(usb)["ok"])
        cilj = self.d / "vraceno"
        self.assertTrue(kop.obnovi(usb, cilj)["ok"])
        self.assertEqual([z["d"]["i"] for z in Dnevnik(cilj, k).citaj()], list(range(5)))
        seg = next((usb / "energija-kopije" / "segmenti").glob("dnevnik__*"))
        seg.write_bytes(seg.read_bytes()[:-3] + b"xyz")
        self.assertFalse(kop.provjeri(usb)["ok"])
        self.assertFalse(Kopije(podaci, os.urandom(32), []).provjeri(usb)["ok"])  # tuđi ključ


# ---------------------------------------------------------------- protokoli
class TestProtokoli(unittest.TestCase):
    def test_modbus_sunspec_otkrivanje(self):
        r = Registri()
        r.postavi("holding", 40000, [0x5375, 0x6E53, 1, 66] + [0] * 66)
        r.postavi("holding", 40004, [0x4142, 0x4300])
        r.postavi("holding", 40070, [103, 50] + [0] * 50)
        r.postavi("holding", 40070 + 14, [2500, 0])
        r.postavi("holding", 40122, [0xFFFF, 0])
        srv = ModbusPosluzitelj({1: r}).pokreni()
        try:
            k = ModbusKlijent("127.0.0.1", srv.port)
            u = probaj_sunspec(k, 1)
            self.assertIsNotNone(u)
            self.assertEqual(u.proizvodjac, "ABC")
            self.assertEqual(u.citaj()["pv_snaga_w"], 2500)
            self.assertIsNone(probaj_sunspec(k, 7))  # nepostojeća jedinica
            k.upisi(1, 100, 42)
            self.assertEqual(k.citaj_holding(1, 100, 1), [42])
        finally:
            srv.zaustavi()

    def test_mqtt_broker_zadrzane_i_zamjenski(self):
        self.assertTrue(odgovara("a/+/c", "a/b/c"))
        self.assertTrue(odgovara("a/#", "a/b/c"))
        self.assertFalse(odgovara("a/+", "a/b/c"))
        b = Broker().pokreni()
        try:
            pub = Klijent("pub", port=b.port).pokreni()
            pub.spojen.wait(3)
            pub.objavi("senzor/z1/vlaga", "31.5", zadrzi=True)
            time.sleep(0.2)
            primljeno = []
            sub = Klijent("sub", port=b.port)
            sub.pri_poruci = lambda t, p: primljeno.append((t, p))
            sub.pokreni()
            sub.spojen.wait(3)
            sub.pretplati("senzor/+/vlaga")
            time.sleep(0.3)
            pub.objavi("senzor/z2/vlaga", "28", qos=1)
            for _ in range(30):
                if len(primljeno) >= 2:
                    break
                time.sleep(0.1)
            self.assertIn(("senzor/z1/vlaga", b"31.5"), primljeno)
            self.assertIn(("senzor/z2/vlaga", b"28"), primljeno)
            pub.zaustavi()
            sub.zaustavi()
        finally:
            b.zaustavi()

    def test_home_assistant_najava(self):
        poslano = []
        u = iz_najave("homeassistant/switch/pumpa/config",
                      json.dumps({"unique_id": "p1", "state_topic": "p/state", "command_topic": "p/set"}).encode(),
                      lambda t, v: poslano.append((t, v)) or True)
        self.assertTrue(u.primi("p/state", b"ON"))
        self.assertEqual(u.citaj(), {"rele_pumpa": 1.0})
        self.assertTrue(u.postavi("rele_pumpa", 0))
        self.assertEqual(poslano, [("p/set", "OFF")])
        s = iz_najave("homeassistant/sensor/tlo1/config",
                      json.dumps({"state_topic": "t/1", "device_class": "moisture"}).encode(), None)
        s.primi("t/1", b"27.5")
        self.assertEqual(s.citaj(), {"tlo1_vlaga": 27.5})


# ---------------------------------------------------------------- impulsno brojilo
class TestImpulsi(unittest.TestCase):
    def test_samoniveliranje_uz_promjenu_svjetla_i_sum(self):
        rng = random.Random(1)
        d = DetektorImpulsa(200)
        stvarnih = 0
        for n in range(200 * 600):  # 10 min
            t = n / 200
            okolina = 600 + 400 * math.sin(t / 120)  # sunce se mijenja na brojilu
            led = 0
            if n % 300 < 8 and n > 400:  # impuls svake 1,5 s, 40 ms
                led = 700
                if n % 300 == 0:
                    stvarnih += 1
            d.uzorak(okolina + led + rng.gauss(0, 12))
        self.assertEqual(d.stanje, "radi")
        self.assertLessEqual(abs(d.impulsi - stvarnih), 2)
        self.assertAlmostEqual(d.ucestalost(), 2400, delta=60)

    def test_nema_signala(self):
        d = DetektorImpulsa(200)
        rng = random.Random(2)
        for _ in range(200 * 20):
            d.uzorak(500 + rng.gauss(0, 5))
        self.assertEqual(d.stanje, "nema_signala")
        self.assertEqual(d.impulsi, 0)

    def test_kalibracija_konstante(self):
        # 2000 imp/kWh: osnova 300 W = 600 imp/h; +2000 W bojler = 4600 imp/h
        self.assertEqual(ImpulsnoBrojilo.kalibriraj(600, 4600, 2000), (2000.0, "kalibrirano"))
        self.assertEqual(ImpulsnoBrojilo.kalibriraj(600, 600, 2000)[1], "pretpostavka")
        self.assertEqual(ImpulsnoBrojilo.kalibriraj(0, 15000, 2000)[1], "kalibrirano-nestandardno")


# ---------------------------------------------------------------- anomalije i prediktivno
class TestAnomalije(unittest.TestCase):
    def test_rad_na_suho_i_baterija(self):
        d = Detektor(cfg())
        for _ in range(10):
            d.obradi({"pumpa_struja_a": 3.4}, 10, {"pumpa": True})
        n = d.obradi({"pumpa_struja_a": 1.0}, 10, {"pumpa": True})
        self.assertTrue(any(a.vrsta == "rad_na_suho" and "pumpa" in a.trosila for a in n))
        n = d.obradi({"baterija_temp_c": 58.0}, 10)
        self.assertTrue(any(a.vrsta == "pregrijavanje" and a.ozbiljnost == "kriticno" for a in n))
        n = d.obradi({"baterija_temp_c": -3.0, "baterija_struja_a": 5.0}, 10)
        self.assertTrue(any(a.vrsta == "punjenje_na_hladnom" for a in n))
        n = d.obradi({"baterija_napon_v": 16 * 2.7}, 10)
        self.assertIn("pastir", {"pastir"} - set(next(a for a in n if a.vrsta == "podnapon").trosila))

    def test_zaglavljen_samo_ako_pratilac_radi(self):
        d = Detektor(cfg())
        for i in range(20):
            d.obradi({"baterija_napon_v": 51.0 + (i % 2) * 0.1, "baterija_struja_a": 0.0}, 600)
        n = d.obradi({"baterija_napon_v": 51.0, "baterija_struja_a": 0.0}, 600)
        self.assertFalse([a for a in n if a.vrsta == "zaglavljen"])  # mirna baterija
        for i in range(15):
            n = d.obradi({"baterija_napon_v": 51.0, "baterija_struja_a": 10.0 + i}, 600)
        self.assertTrue([a for a in n if a.vrsta == "zaglavljen"])

    def test_trend_predvidja(self):
        t = Trend()
        for dan in range(10):
            t.dodaj(dan, 6.0 - 0.1 * dan)
        self.assertAlmostEqual(t.dana_do(4.0, raste=False), 11, delta=0.5)
        d = Detektor(cfg())
        for dan in range(10):
            d.dnevni_pokazatelji(dan, {"pastir_min_kv": 6.0 - 0.1 * dan})
        z = d.predvidi()
        self.assertEqual(z[0]["pokazatelj"], "pastir_min_kv")


# ---------------------------------------------------------------- pastir
class TestPastir(unittest.TestCase):
    """Električni model ograde kao u simulaciji: G vodljivost, prsten preko R."""

    def model(self, p: Pastir, kratki=None, prekid=None, aparat_ok=True):
        n = p.n
        dos = {0}
        promjena = True
        while promjena:
            promjena = False
            for k in range(1, n + 1):
                if p.sklopke[k] and prekid != k and ((k - 1 in dos) != (k in dos)):
                    dos |= {k - 1, k}
                    promjena = True
            if p.r_zatvoren and n not in dos:
                dos.add(n)
                promjena = True
        G = sum((0.5 if kratki == k else 0.002) for k in range(1, n + 1)
                if (k - 1 in dos and p.sklopke[k]) or k in dos)
        v0 = (9.0 if aparat_ok else 0.5) / (1 + 20 * G)
        return [v0] + [v0 if k in dos else 0.0 for k in range(1, n + 1)]

    def vrti(self, p, koraka, **kv):
        out, ts = None, getattr(self, "ts", 0.0)
        for _ in range(koraka):
            ts += 10
            out = p.korak(ts, 10, self.model(p, **kv), 0.9, 0.6, False, 0.3)
        self.ts = ts
        return out

    def test_kratki_spoj_izoliran_ostatak_iz_prstena(self):
        for f in (1, 2, 3, 4):
            self.ts = 0.0
            p = Pastir(cfg(), 4, True)
            self.vrti(p, 3)
            out = self.vrti(p, 8, kratki=f)
            self.assertEqual(p.nacin, "izolirano", f)
            self.assertEqual(p.kvar_dionica, f)
            v = self.model(p, kratki=f)
            self.assertGreaterEqual(v[0], 4.0)
            ostale = [v[k] for k in range(1, 5) if k != f]
            self.assertTrue(all(x >= 4.0 for x in ostale), (f, v))
            self.assertEqual(out["dionice"][f - 1], "izolirana")

    def test_prekid_premosten_i_oporavak(self):
        self.ts = 0.0
        p = Pastir(cfg(), 4, True)
        self.vrti(p, 3)
        self.vrti(p, 3, prekid=2)
        self.assertEqual(p.nacin, "prekid")
        self.assertTrue(p.r_zatvoren)
        self.assertTrue(all(x >= 4 for x in self.model(p, prekid=2)[3:]))
        self.vrti(p, 100)  # žica popravljena, ponovni test nakon 15 min
        self.assertEqual(p.nacin, "normalno")
        self.assertFalse(p.r_zatvoren)

    def test_bez_prstena_i_kvar_aparata(self):
        self.ts = 0.0
        p = Pastir(cfg(), 4, False)
        self.vrti(p, 3)
        self.vrti(p, 8, kratki=2)
        self.assertEqual((p.nacin, p.kvar_dionica), ("izolirano", 2))
        self.assertFalse(p.sklopke[2])
        self.ts = 0.0
        p = Pastir(cfg(), 4, True)
        self.vrti(p, 6, aparat_ok=False)
        self.assertEqual(p.nacin, "kvar_aparata")

    def test_stedni_impuls_s_histerezom(self):
        self.ts = 0.0
        p = Pastir(cfg(), 4, True)
        snage = [self.vrti(p, 1)["snaga"] for _ in range(6)]
        self.assertEqual(snage[-1], 0.6)
        self.assertEqual(len(set(snage[2:])), 1)  # ne titra


# ---------------------------------------------------------------- učenje, optimizacija, navodnjavanje
class TestOdluke(unittest.TestCase):
    def test_ucenje_navika(self):
        n = Navike()
        pocetak = time.mktime((2026, 3, 2, 0, 0, 0, 0, 0, -1))  # ponedjeljak
        for tjedan in range(3):
            for s in range(7 * 24 * 6):
                ts = pocetak + tjedan * 7 * 86400 + s * 600
                lt = time.localtime(ts)
                prisutni = lt.tm_wday == 5 and 8 <= lt.tm_hour < 22
                n.dodaj(ts, 900.0 if prisutni else 60.0, 600)
        petak = pocetak + 3 * 7 * 86400 + 4 * 86400 + 12 * 3600
        p = n.parametri(petak, cfg())
        self.assertEqual(p["sljedeci_dolazak_h"], 20)  # subota 8 h
        self.assertGreater(p["rezerva_soc"], cfg()["baterija"]["soc_min"])
        self.assertLess(n.osnova_w, 120)

    def test_punjenje_iz_jeftine_mreze(self):
        c = cfg()
        c["baterija"]["trosak_ciklusa_eur_kwh"] = 0.01
        cijene = [{"kupnja": 0.05 if h < 4 else 0.40, "prodaja": 0.02} for h in range(12)]
        plan = planiraj_bateriju([1500.0] * 12, [0.0] * 12, cijene, 0.2, c, 0.15, 0)
        self.assertGreater(sum(p["baterija_kw"] for p in plan[:4]), 2)
        self.assertLess(sum(p["baterija_kw"] for p in plan[4:]), -2)
        osn = osnovni_scenarij([1500.0] * 12, [0.0] * 12, cijene, 0.2, c)
        self.assertLess(sum(p["trosak_eur"] for p in plan), osn["trosak_eur"])

    def test_otocno_cuva_opskrbu(self):
        c = cfg()
        c["mreza"]["dostupna"] = False
        plan = planiraj_bateriju([300.0] * 10, [0.0] * 10, [{"kupnja": 0.1, "prodaja": 0.0}] * 10, 0.6, c, 0.15, 0)
        self.assertTrue(all(p["mreza_kw"] <= 1e-6 for p in plan))

    def test_fleksibilno_u_visak_sunca(self):
        pv = [0.0] * 8 + [3000.0] * 6 + [0.0] * 10
        cijene = [{"kupnja": 0.16, "prodaja": 0.05}] * 24
        c = cfg()
        _, r = smjesti_fleksibilna([200.0] * 24, pv, cijene,
                                   [{"id": "bojler", "snaga_w": 2000, "energija_kwh": 4, "od_h": 0, "do_h": 24}], 0.9, c)
        self.assertTrue(all(8 <= h < 14 for h in r["bojler"]), r)

    def test_navodnjavanje_kisa_i_suho(self):
        c = cfg()
        n = Navodnjavanje(c)
        ts = time.mktime((2026, 6, 1, 6, 0, 0, 0, 0, -1))
        r = n.korak(ts, {"z1": 24.0}, 8.0, False, True)
        self.assertFalse(r["pumpa"])
        self.assertIn("kiše", r["razlog"])
        self.assertGreater(n.ustedjeno_min, 0)
        r = n.korak(ts + 60, {"z1": 24.0}, 0.0, False, True)
        self.assertTrue(r["pumpa"])
        r = n.korak(ts + 1200, {"z1": 43.0}, 0.0, False, True)
        self.assertFalse(r["pumpa"])
        self.assertEqual(n.dnevnik[-1]["zona"], "z1")
        r = n.korak(ts + 1300, {"z1": 20.0}, 0.0, False, False)
        self.assertFalse(r["pumpa"])  # zaštita/baterija ima prednost


# ---------------------------------------------------------------- tunel, oblak, nadzor
class TestDaljinski(Privremeno):
    def test_tunel_preko_releja_kraj_do_kraja(self):
        tj, tk, tz = Trezor(self.d / "j"), Trezor(self.d / "k"), Trezor(self.d / "z")
        relej = Relej().pokreni()
        jezgra = TunelJezgre(tj, lambda: {tk.javni_potpisni}, lambda z: {"echo": z["put"]})
        jezgra.preko_releja("127.0.0.1", relej.port, None)
        try:
            for _ in range(50):
                if tj.id_uredaja() in relej.cekaju:
                    break
                time.sleep(0.05)
            k = TunelKlijent(tk.potpisni, tj.javni_potpisni).spoji_relej("127.0.0.1", relej.port, tj.id_uredaja(), None)
            self.assertEqual(k.zahtjev({"put": "/api/stanje"}), {"echo": "/api/stanje"})
            k.zatvori()
            for _ in range(50):
                if tj.id_uredaja() in relej.cekaju:
                    break
                time.sleep(0.05)
            uljez = TunelKlijent(tz.potpisni, tj.javni_potpisni)
            with self.assertRaises(Exception):
                uljez.spoji_relej("127.0.0.1", relej.port, tj.id_uredaja(), None)
                uljez.zahtjev({"put": "/api/stanje"})
        finally:
            jezgra.zaustavi()
            relej.zaustavi()

    def test_sinkronizacija_sifrirano_i_offline(self):
        t = Trezor(self.d)
        d = Dnevnik(self.d / "a", t.kljuc("arhiva"))
        for i in range(7):
            d.zapisi("sat", {"i": i, "tajno": "potrosnja"})
        primljeno, mreza = [], {"radi": False}

        def posalji(put, tijelo):
            if not mreza["radi"]:
                raise OSError("nema mreže")
            primljeno.append(json.loads(tijelo))
            return 200, b""

        s = Sinkronizacija(cfg(), t, d, posalji=posalji)
        r = s.korak(1000.0, najvise=5)
        self.assertIn("greska", r)
        self.assertEqual(s.pokazivac, 0)
        mreza["radi"] = True
        self.assertEqual(s.korak(1000.0 + 60, najvise=5)["poslano"], 5)
        self.assertEqual(s.korak(2000.0, najvise=5)["poslano"], 2)
        self.assertEqual(s.pokazivac, 7)
        self.assertNotIn(b"potrosnja", json.dumps(primljeno).encode())

    def test_neovlastene_postavke_se_odbacuju(self):
        t, vlasnik = Trezor(self.d / "j"), Trezor(self.d / "v")
        s = Sinkronizacija(cfg(), t, None, {"vlasnik": vlasnik.javni_potpisni.hex()}, posalji=lambda *a: (200, b""))
        import base64
        post = {"tarifa": {"vt_eur_kwh": 0.2}, "baterija": {"soc_min": 0.0}}
        potpis = base64.b64encode(vlasnik.potpisi(json.dumps(post, sort_keys=True).encode())).decode()
        s._primi_postavke(json.dumps({"postavke": post, "potpis": potpis}).encode())
        self.assertEqual(s.predlozene, {"tarifa": {"vt_eur_kwh": 0.2}})  # baterija je zaštićena
        s.predlozene = None
        s._primi_postavke(json.dumps({"postavke": post, "potpis": base64.b64encode(b"x" * 64).decode()}).encode())
        self.assertIsNone(s.predlozene)

    def test_nadzornik_sigurno_stanje(self):
        stanje = {"sigurno": 0, "pozivi": 0}

        def pada():
            stanje["pozivi"] += 1
            raise RuntimeError("senzor")

        n = Nadzornik(sigurno_stanje=lambda: stanje.__setitem__("sigurno", stanje["sigurno"] + 1))
        n.dodaj("kriticni", pada, 0.0, kriticno=True)
        for _ in range(200):
            n.jednom()
            for z in n.zadaci.values():
                if z.nit:
                    z.nit.join()
                z.sljedece = 0
            if n.u_sigurnom:
                break
        self.assertTrue(n.u_sigurnom)
        self.assertEqual(stanje["sigurno"], 1)
        self.assertGreaterEqual(stanje["pozivi"], 3)


# ---------------------------------------------------------------- cijela jezgra
class TestJezgra(Privremeno):
    def test_simulacija_oporavak_i_izvjestaj(self):
        from jezgra.__main__ import brza_simulacija

        j, izv = brza_simulacija(self.d, 2.0, korak_s=60.0, ispis=False, sezona="zima")
        self.assertEqual(izv["pouzdanost"]["pastir_automatskih_izolacija"], 1)  # kratki spoj 1,4. dan
        self.assertEqual(j.brojilo.konstanta, 2000.0)
        self.assertEqual(izv["razdoblje"]["sati_podataka"], 48)
        u = izv["procjena_ustede"]
        self.assertLessEqual(u["s_upravljanjem_eur"], u["osnovica_eur"] + 0.10)  # nikad bitno lošije od osnovice
        for ext in ("html", "json", "csv", "potpis.json"):
            self.assertTrue((self.d / "izvjestaji" / f"simulacija.{ext}").exists())
        potpis = json.loads((self.d / "izvjestaji" / "simulacija.potpis.json").read_text())
        spremljen = json.loads((self.d / "izvjestaji" / "simulacija.json").read_text())
        self.assertTrue(provjeri(spremljen, potpis))
        spremljen["procjena_ustede"]["usteda_eur"] += 100
        self.assertFalse(provjeri(spremljen, potpis))
        self.assertTrue(any(k["ok"] for k in j.kopije.zadnje.values()))

    def test_pad_bez_gubitka_satnih_podataka(self):
        from jezgra.__main__ import SimSat
        from jezgra.jezgra import Jezgra
        from jezgra.simulacija import Lokacija, izravni_uredaji

        def pokreni(mapa, padni_na):
            c = cfg()
            pocetak = time.mktime((2026, 1, 12, 0, 0, 0, 0, 0, -1))
            lok = Lokacija(c, pocetak, kvarovi=False)
            sat = SimSat(pocetak)
            j = Jezgra(mapa, c, sat=sat, uredaji=izravni_uredaji(lok), dohvati_prognozu=lok.prognoza_api)
            for i in range(int(6 * 3600 / 60)):
                if i == padni_na:
                    j.dnevnik.sinkroniziraj()  # ono što je fsync-ano preživi; snimka je starija
                    j = Jezgra(mapa, c, sat=sat, uredaji=izravni_uredaji(lok), dohvati_prognozu=lok.prognoza_api)
                    self.assertGreater(j.oporavak["ponovljeno_zapisa"], 0)
                lok.korak(60)
                sat.t = lok.t
                j.korak()
            j.zatvori()
            return [(s["ts"], round(s["potrosnja_kwh"], 6), round(s["pv_kwh"], 6)) for s in j.sati]

        bez = pokreni(self.d / "a", None)
        s_padom = pokreni(self.d / "b", 197)  # usred 4. sata, 2 min nakon snimke
        self.assertEqual(len(bez), 6)
        self.assertEqual(bez, s_padom)


if __name__ == "__main__":
    unittest.main()
