"""Razvrstavanje u grupe: jednaka pravila za sve grupe (stvarni nazivi iz cjenika 5.11.2026.).

Vlasnik je za "mlijeko" dobio proizvod koji nije mlijeko. Uzrok: riječ grupe bilo gdje u nazivu svrstavala je
proizvod u grupu ("Posuda za mlijeko", "Gel med i mlijeko", "Desert od bivoljeg mlijeka"). Sada vrstu određuje
prva riječ vrste, riječ iza "za/s/od/i..." ne određuje vrstu, a neprehrambene riječi isključuju prehrambene grupe.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "uvoz"))
import uvoz  # noqa: E402

R = uvoz.Razvrstavanje()
ID = [g["id"] for g in R.grupe]


def grupa(naziv, marka=""):
    g = R.razvrstaj(naziv, marka)[0]
    return ID[g] if g >= 0 else None


class PraviProizvodiOstaju(unittest.TestCase):
    def test_mlijeko(self):
        for n in ["Mlijeko trajno 2,8%", "Dukat trajno mlijeko 2.8% 1l boca", "KLC.Trajno mlijeko 3,5%m.m.1L",
                  "Alpsko mlijeko 1,5% bez laktoze", "'z bregov Svježe mlijeko 1,5% m.m.", "Mlijeko kozje 2,8% mm"]:
            self.assertEqual(grupa(n), "mlijeko", n)

    def test_ostale_osnovne_namirnice(self):
        primjeri = {
            "Jogurt tekući 2,8% 1 kg": "jogurt", "Jogurt s mlijekom": "jogurt", "B.Aktiv Natur Jogurt": "jogurt",
            "Kruh polubijeli 500 g": "kruh", "S.kruh s maslinama 300 g": "kruh", "Kukuruzni miješani kruh": "kruh",
            "Graham pecivo": "peciva", "Vanilin kiflice": "peciva", "Hot dog pecivo": "peciva",
            "Tamna čokolada 72% kakao 100g": "cokolada", "Milka čokolada mliječna": "cokolada",
            "Čokol dorin 160 g mlijeko": "cokolada", "Kakao napitak 400 g": "napici",
            "Čokoladno mlijeko bijela čokolada": "napici",
            "TUNJ KOMADI U SUNC ULJU": "riba", "Suseni atlantski bakalar": "riba", "Smrznuti orada filet": "riba",
            "Tuna u ulju": "riba", "Maslinovo ulje 1l": "ulje", "Riža basmati 1 kg": "riza",
            "Zlatna Džezva mljevena kava": "kava", "Zdjelarević graševina": "vino", "Prošper desertno vino": "vino",
            "Jana Ledeni Čaj Breskva": "caj", "Kisela voda Jamnica": "voda", "Fanta naranča 1,5 l": "sok",
            "Grah s kobasicom": "grah", "Kukuruz šećerac": "zimnica", "High Protein Jogurt": "jogurt",
            "Paprika crvena babura": "paprika", "Paprika mljevena slatka 100 g": "zacini", "Paprika salama": "suhomesnato",
            "Frank’s Umak RedHot": "zacini", "Mlijeko Hipp 1 Bio Combiotik": "bebe", "Pedigree hrana za pse": "ljubimci",
        }
        for n, g in primjeri.items():
            self.assertEqual(grupa(n), g, n)


class TudjiProizvodiNisuUGrupi(unittest.TestCase):
    def test_nista_od_ovoga_nije_mlijeko(self):
        for n in ["Posuda za mlijeko 600 ml", "Vrč za mlijeko 0,5 l", "Lončić za mlijeko 14x12cm geneva",
                  "Šlag pjena s mlijekom", "Desert od bivoljeg mlijeka pistacija120g", "Balea gel med i mlijeko",
                  "Prens ts 5l med&mlijeko", "SUNDANCE mlijeko za sunč. ZF30 200 ml", "Mlijeko nivea hranjivo 500ml",
                  "Avene XeraCalm Nutr.hidr. mlijeko 400 ml", "DB mačka pilet./mlijeko 100g T", "Tortina mlijeko 200 g oho!",
                  "Milka Waffelini Mlijeko", "AliBaba Mlijeko zaslađ.kond.8,8%m.m.397g", "Set mlijeko i šećer bijeli",
                  "Pjenjač mlijeka 0,8l", "Namaz finesse duo lješnjak mlijeko 400 g", "Bombon tvrdi s mlijekom 90g"]:
            self.assertNotEqual(grupa(n), "mlijeko", n)

    def test_neprehrambeno_nikad_u_prehrambenoj_grupi(self):
        hrana = {g["id"] for g in R.grupe if g.get("hrana", True)}
        for n in ["Zub.pasta sensodyne 75 ml", "Lukky lak za nokte", "Stolnjak fantastik pvc 120",
                  "Polzela hh eva elegance 9300 20den vel.3 crna sir", "essence ulje/usne Hydra Kiss",
                  "Lampice led riža 60 funkcija", "Chicco grizalo silikon", "Parf. voda žen. secret moon 100ml",
                  "Posipač šećera", "Mlinac papar i sol", "Zdjela za grickalice"]:
            self.assertNotIn(grupa(n), hrana, n)

    def test_hrana_za_ljubimce_nije_hrana_za_ljude(self):
        for n in ["Kitty mm puretina pačetina 405g", "One Mini Adult Piletina Riža"]:
            self.assertEqual(grupa(n), "ljubimci", n)


class Pravila(unittest.TestCase):
    def test_prva_rijec_vrste_odlucuje(self):
        self.assertEqual(grupa("Jogurt čokolada"), "jogurt")
        self.assertEqual(grupa("Keks s čokoladom"), "keksi")
        self.assertEqual(grupa("Čokolada s keksom"), "cokolada")

    def test_rijec_iza_ovisne_ne_odlucuje(self):
        self.assertEqual(grupa("Čaj bez šećera"), "caj")
        self.assertIsNone(grupa("Okruglice od kruha"))      # bolje bez grupe nego "kruh"

    def test_marka_vrijedi_tek_bez_rijeci_vrste(self):
        self.assertEqual(grupa("Milka Oreo"), "slatkisi")
        self.assertEqual(grupa("Jana voda 1,5 l"), "voda")


class StvarniPobjedniciPoLancima(unittest.TestCase):
    """Proizvodi koji su 5.11.2026. bili "najjeftiniji" u nekom lancu, a nisu ta namirnica (provjera svih lanaca)."""

    def test_nisu_ta_namirnica(self):
        krivo = {
            "Jaja 6 kom 504402 offert.": "jaja", "JAJA stiropor 12 kom 5 cm OFFERTISSIMA": "jaja",
            "Kavabon Bombon rolica": "kava", "Coffee creamer 150g": "kava", "Tres chic kava sa šlagom 180 g vindija": "kava",
            "Instant Kava Ice Coffee": "kava", "Šumi trdi bon kava bombon 48g": "kava",
            "Zamjes za ječmeni kruh": "kruh", "Bake rolls sir 80 g": "sir", "Tijes rezan dom šir jaj 400 g marodi": "sir",
            "Sportness pr.ploč. 36% lim.-sir 40 g": "sir",
            "Artu mp 1230 g piletina": "piletina", "Moustache mm 415 g piletina": "piletina", "Pileće kosti": "piletina",
            "Pileća leđa s budget": "piletina", "Posebna pileća 1000 g to je to": "piletina", "Pileća jetra sa srcem 500g": "piletina",
            "Svinjske kožice": "meso", "Meso junet kg loj": "meso", "Svinjski bubreg HR": "meso", "Svinjska glava": "meso",
            "Wise cat 100 g govedina vrecica": "meso", "Svinjske nogice kg": "meso",
            "Banan.čoko.per.150 g kraš": "banane", "Luk prženi": "luk", "Lukovice u octu": "luk", "Kapulica sjemenska žuta 1kg": "luk",
            "Rajčica pasir 500 ml kuharela": "rajcica", "Tjes.kuk.riža alb go.bg.250 g": "riza",
            "Karl Lagerfeld Classic edt 100 ml": "pivo", "Organic S.piling/tijPearl Rose 250 ml": "vino",
            "Fentimans Rose Lemonade": "vino", "Uže za rublje 10m art:20280402 ntl": "deterdzent",
            "Sušilo za rublje diciotto 18 m": "deterdzent", "Riblja utroba otpis": "riba", "Sv.kožice rfs pik": "riba",
            "Mg mm gov grašak mrkva 85 g vr": "grah", "Pud.s-budget čokolada 3x40 g": "cokolada",
            "Denkmit voda za glačalo 1 l": "voda", "Mivolis sol/kupanje iz Mrtvog mora 1,5kg": "sol",
            "dmBio voćna kaš. egz.b.müsli, 8+mj,190g": "zitarice", "Oblatne 200g": "keksi",
        }
        for naziv, nije in krivo.items():
            self.assertNotEqual(grupa(naziv), nije, naziv)

    def test_prave_namirnice_ostaju(self):
        dobro = {
            "Jaja M razred": "jaja", "Kava Momento mljevena": "kava", "Jubilarna kava mljevena": "kava",
            "Kruh polubijeli 500g tkz": "kruh", "Sir svježi posni Protein": "sir", "Svježe pile, cca. 1,5kg": "piletina",
            "Pileći batak": "piletina", "Svinjski kare odresci sk, cca. 1kg": "meso", "Banane": "banane", "Luk crveni": "luk",
            "Rajčica": "rajcica", "Riža dugo zrno": "riza", "Löwenbräu Svijetlo pivo": "pivo", "Graševina Ultra": "vino",
            "Srdela cijela": "riba", "Grašak sušeni": "grah", "Kuhinjska sol": "sol", "Zobene pahuljice": "zitarice",
            "Petit keksi": "keksi", "Persil deterdžent za rublje": "deterdzent",
        }
        for naziv, je in dobro.items():
            self.assertEqual(grupa(naziv), je, naziv)


if __name__ == "__main__":
    unittest.main()
