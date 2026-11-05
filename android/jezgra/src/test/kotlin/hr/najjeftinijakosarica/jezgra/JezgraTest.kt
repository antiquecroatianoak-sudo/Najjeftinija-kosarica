package hr.najjeftinijakosarica.jezgra

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Ispitni katalog generira scripts/app_katalog.cjs (node tests/app-katalog.cjs --zapisi); cijene nisu stvarne. */
class JezgraTest {
    private val k = Katalog.izJsona(javaClass.getResource("/katalog-test.json")!!.readText())
    private val svi = k.lanci.indices.toSet()
    private val KONZUM = 0
    private val LIDL = 1
    private val KAUFLAND = 2
    private fun s(t: String) = Upit.razumi(t, k)
    private fun najbolja(t: String, lanci: Set<Int> = svi) = Racun.izracunaj(s(t), k, lanci).ponude.first()

    @Test fun ucitavanje() {
        assertEquals(listOf("Konzum", "Lidl", "Kaufland"), k.lanci)
        assertEquals("5.11.2026.", k.datumPrikaz)
        assertEquals(11, k.proizvodi.size)
    }

    @Test fun normalizacija() {
        assertEquals("cokoladno mlijeko", Tekst.normaliziraj("Čokoladno  mlijeko!"))
        assertEquals("dzem", Tekst.normaliziraj("Džem"))
        assertEquals(listOf("1d5", "l", "mlijeka"), Tekst.rijeci("1,5 l mlijeka"))
        assertEquals("mlijek", Tekst.korijen("mlijeko"))
        assertEquals("1,99 €", Tekst.eura(199))
        assertEquals("1.234,50 €", Tekst.eura(123450))
        assertEquals("500 g", Tekst.kolicina(0.5, "kg"))
        assertEquals("1,5 l", Tekst.kolicina(1.5, "l"))
    }

    @Test fun razdvajanjePopisa() {
        assertEquals(listOf("kruh", "2 mlijeka", "deset jaja", "banane"), Upit.razdvoji("Kruh, 2 mlijeka, deset jaja i banane"))
    }

    @Test fun samoSkupinaTraziSveVrsteIZadanuKolicinu() {
        val m = s("mlijeko")
        assertEquals("mlijeko", m.grupa?.id)
        assertTrue(m.zadanaKolicina)
        assertEquals(Kolicina(1.0, 1), m.kolicina)
        // 1 l: Z bregov u Konzumu 0,95 € pobjeđuje dva pakiranja trajnog od 0,5 l (0,90 €)? Ne: 2 × 0,45 = 0,90 € je jeftinije.
        val b = najbolja("mlijeko")
        assertEquals("Mlijeko trajno 0,5 l", b.proizvod.naziv)
        assertEquals(2, b.pakiranja)
        assertEquals(90, b.ukupnoCenti)
    }

    @Test fun podvrstaIMarka() {
        assertEquals("Kruh crni 700 g", najbolja("crni kruh").proizvod.naziv)
        val d = najbolja("Dukat mlijeko")
        assertEquals("Dukat mlijeko 2,8% m.m. 1 l", d.proizvod.naziv)
        assertEquals(LIDL, d.cijena.lanac)
        assertTrue(d.cijena.akcija)
        // Biljno mlijeko nije obično mlijeko.
        assertEquals("biljno-mlijeko", s("zobeno mlijeko").grupa?.id)
        assertTrue(Racun.ponude(s("mlijeko"), k, svi).none { it.proizvod.naziv.startsWith("Zobeno") })
    }

    @Test fun kolicineIGovor() {
        assertEquals(Kolicina(2.0, 1), s("2 litre mlijeka").kolicina)
        assertEquals(Kolicina(2.0, 1), s("dvije litre mlijeka").kolicina)
        assertEquals(Kolicina(0.5, 0), s("pola kile sira").kolicina)
        assertEquals(Kolicina(6.0, 2), s("6 jaja").kolicina)
        assertEquals(Kolicina(1.5, 1), s("1,5 l mlijeka").kolicina)
        assertEquals(Kolicina(1.0, 0), s("kilu sira").kolicina)
        assertEquals(Kolicina(2.0, 1), s("2 mlijeka").kolicina)
        assertEquals("rajcica", s("paradajz").grupa?.id)
        assertFalse(s("6 jaja").zadanaKolicina)
    }

    @Test fun najmanjiTrosakZaKolicinu() {
        // 6 jaja: pakiranje od 6 (1,69 €) jeftinije je od pakiranja od 10 (2,29 €).
        assertEquals("Jaja L 6 kom", najbolja("6 jaja").proizvod.naziv)
        // 10 jaja: 10 kom za 2,29 € jeftinije od 2 × 6 kom (3,38 €).
        assertEquals("Jaja M 10 kom", najbolja("jaja").proizvod.naziv)
        // Pola kile sira: svježi 250 g × 2 = 2,38 € (Lidl) jeftinije od gaude 400 g × 2.
        val sir = najbolja("pola kile sira")
        assertEquals("Sir svježi 250 g", sir.proizvod.naziv)
        assertEquals(2, sir.pakiranja)
        assertEquals(238, sir.ukupnoCenti)
        assertEquals(476, sir.jedinicnaCenti)
    }

    @Test fun odabirLanaca() {
        val b = najbolja("mlijeko", setOf(KONZUM))
        assertEquals(KONZUM, b.cijena.lanac)
        assertEquals("Z bregov mlijeko 1 l", b.proizvod.naziv)
    }

    @Test fun istaStavkaSeSpaja() {
        val spojeno = Upit.spoji(listOf(s("mlijeko"), s("mlijeko")))
        assertEquals(1, spojeno.size)
        assertEquals(Kolicina(2.0, 1), spojeno[0].kolicina)
    }

    @Test fun nepronadenoNikadTiho() {
        val r = Racun.izracunaj(s("plavi kruh"), k, svi)
        assertTrue(r.ponude.isEmpty())
        assertTrue(r.prijedlozi.isNotEmpty())
        val n = Racun.izracunaj(s("xyzzy"), k, svi)
        assertNull(n.stavka.grupa)
        assertTrue(n.ponude.isEmpty())
    }

    @Test fun sveUJednomLancuIUsteda() {
        val popis = listOf("mlijeko", "kruh", "jaja").map { Racun.izracunaj(s(it), k, svi) }
        val lanci = Racun.poLancima(popis, svi)
        // Konzum i Lidl imaju sve tri stavke; Kaufland nema kruh. Lidl 4,47 € ispred Konzuma 5,62 €.
        val potpuni = lanci.filter { it.nedostaje.isEmpty() }.map { it.lanac }.toSet()
        assertEquals(setOf(KONZUM, LIDL), potpuni)
        assertEquals(listOf(LIDL, KONZUM), lanci.take(2).map { it.lanac })
        assertEquals(447, lanci[0].ukupnoCenti)
        val kaufland = lanci.first { it.lanac == KAUFLAND }
        assertEquals(listOf("kruh"), kaufland.nedostaje.map { it.tekst })
        // Nepotpuni lanac nikad ispred potpunog, čak ni kad mu je zbroj manji.
        assertTrue(lanci.indexOf(kaufland) > lanci.indexOfFirst { it.nedostaje.isEmpty() })
        val ukupno = popis.sumOf { it.ponude.first().ukupnoCenti }
        val usteda = Racun.usteda(ukupno, lanci)
        assertNotNull(usteda)
        assertTrue(usteda > 0)
    }

    @Test fun nemaPretvorbeJedinica() {
        // "2 kg mlijeka": mlijeko je u litrama, kg se ne pretvara u l.
        assertTrue(Racun.ponude(s("2 kg mlijeka"), k, svi).isEmpty())
    }
}
