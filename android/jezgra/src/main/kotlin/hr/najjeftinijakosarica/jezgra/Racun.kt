package hr.najjeftinijakosarica.jezgra

import kotlin.math.ceil

/** Jedna mogućnost kupnje za stavku: proizvod u lancu, broj pakiranja i ukupna cijena. */
data class Ponuda(
    val proizvod: Proizvod,
    val cijena: Cijena,
    val pakiranja: Int,
    val ukupnoCenti: Long,
) {
    /** Cijena po kg / l / kom, u centima. */
    val jedinicnaCenti: Long get() = Math.round(cijena.centi / proizvod.iznos)
}

data class RezultatStavke(
    val stavka: Stavka,
    /** Sve ponude od najjeftinije; prazno = nije pronađeno. */
    val ponude: List<Ponuda>,
    /** Prijedlozi kad ništa ne odgovara (najbliži proizvodi iste skupine ili po riječima). */
    val prijedlozi: List<Proizvod>,
)

data class Lanac(
    val lanac: Int,
    val ukupnoCenti: Long,
    val stavke: List<Pair<Stavka, Ponuda?>>,
) {
    val nedostaje: List<Stavka> get() = stavke.filter { it.second == null }.map { it.first }
}

object Racun {
    private const val EPS = 1e-9

    /** Proizvodi koji odgovaraju stavci (vrsta + sve dodatne riječi), bez obzira na lanac. */
    fun clanovi(s: Stavka, k: Katalog): List<Proizvod> {
        val g = s.grupa ?: return emptyList()
        val skupina = k.poGrupi[g.indeks].orEmpty() +
            (if (g.id == "kruh") k.grupaPoId["tost"]?.let { k.poGrupi[it.indeks] }.orEmpty() else emptyList())
        return skupina.filter { p -> s.dodatno.all { kor -> p.rijeci.any { Tekst.odgovara(it, kor, k.nastavci) } } }
    }

    /** Sve ponude za stavku u dopuštenim lancima, od najniže ukupne cijene za traženu količinu. */
    fun ponude(s: Stavka, k: Katalog, lanci: Set<Int>): List<Ponuda> {
        val kol = s.kolicina
        val izlaz = ArrayList<Ponuda>()
        for (p in clanovi(s, k)) {
            // Nema izmišljene pretvorbe: kg se ne miješa s l ni s komadima.
            if (kol != null && p.jedinica != kol.jedinica) continue
            val komada = if (kol == null) 1 else maxOf(1, ceil(kol.iznos / p.iznos - EPS).toInt())
            for (c in p.cijene) if (c.lanac in lanci) izlaz.add(Ponuda(p, c, komada, c.centi * komada))
        }
        izlaz.sortWith(compareBy<Ponuda> { it.ukupnoCenti }.thenBy { it.jedinicnaCenti }.thenBy { it.proizvod.naziv })
        return izlaz
    }

    fun izracunaj(s: Stavka, k: Katalog, lanci: Set<Int>): RezultatStavke {
        val p = ponude(s, k, lanci)
        if (p.isNotEmpty()) return RezultatStavke(s, p, emptyList())
        // Nije pronađeno: nikad se ne preskače tiho. Prijedlog = najjeftinije iz iste skupine ili po riječima.
        val prijedlozi = if (s.grupa != null) {
            k.poGrupi[s.grupa.indeks].orEmpty().filter { pr -> pr.cijene.any { it.lanac in lanci } }
                .sortedBy { pr -> pr.cijene.filter { it.lanac in lanci }.minOf { it.centi } / pr.iznos }
        } else {
            val korijeni = Tekst.rijeci(s.tekst).filter { it.length > 2 }.map { Tekst.korijen(it) }
            k.proizvodi.filter { pr -> pr.cijene.any { it.lanac in lanci } && korijeni.any { kor -> pr.rijeci.any { Tekst.odgovara(it, kor, k.nastavci) } } }
                .sortedByDescending { pr -> korijeni.count { kor -> pr.rijeci.any { Tekst.odgovara(it, kor, k.nastavci) } } }
        }
        return RezultatStavke(s, emptyList(), prijedlozi.distinctBy { it.naziv }.take(3))
    }

    /** "Sve u jednom lancu": za svaki lanac zbroj najjeftinijih ponuda; potpuni lanci prvi, zatim po zbroju. */
    fun poLancima(rezultati: List<RezultatStavke>, lanci: Set<Int>): List<Lanac> =
        lanci.map { l ->
            val stavke = rezultati.map { r -> r.stavka to r.ponude.firstOrNull { it.cijena.lanac == l } }
            Lanac(l, stavke.sumOf { it.second?.ukupnoCenti ?: 0L }, stavke)
        }.sortedWith(compareBy<Lanac> { it.nedostaje.size }.thenBy { it.ukupnoCenti })

    /** Ušteda prema najskupljem lancu koji ima cijeli popis (null ako ga nema ili nema uštede). */
    fun usteda(najjeftinijeUkupno: Long, lanci: List<Lanac>): Long? {
        val najskuplji = lanci.filter { it.nedostaje.isEmpty() }.maxOfOrNull { it.ukupnoCenti } ?: return null
        return (najskuplji - najjeftinijeUkupno).takeIf { it > 0 }
    }
}
