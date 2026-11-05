package hr.najjeftinijakosarica.jezgra

/** Količina u osnovnoj jedinici kataloga: indeks u katalog.jedinice (0 kg, 1 l, 2 kom). */
data class Kolicina(val iznos: Double, val jedinica: Int)

/** Jedna stavka popisa, onako kako ju je aplikacija razumjela. */
data class Stavka(
    val tekst: String,
    val grupa: Grupa?,
    /** Korijeni dodatnih riječi (podvrsta, marka, okus) koje proizvod mora sadržavati. */
    val dodatno: List<String>,
    val kolicina: Kolicina?,
    /** true kad korisnik nije rekao količinu pa je uzeta zadana količina skupine. */
    val zadanaKolicina: Boolean,
) {
    /** Ključ za spajanje iste stavke (mlijeko dvaput = 2 l). */
    val kljuc: String get() = (grupa?.id ?: "?") + "|" + dodatno.sorted().joinToString(" ") + "|" + (kolicina?.jedinica ?: -1)
}

object Upit {
    private val brojevi = mapOf(
        "jedan" to 1.0, "jedna" to 1.0, "jedno" to 1.0, "jednu" to 1.0, "jednog" to 1.0,
        "dva" to 2.0, "dvije" to 2.0, "dvoje" to 2.0, "tri" to 3.0, "troje" to 3.0, "cetiri" to 4.0, "pet" to 5.0,
        "sest" to 6.0, "sedam" to 7.0, "osam" to 8.0, "devet" to 9.0, "deset" to 10.0, "jedanaest" to 11.0,
        "dvanaest" to 12.0, "petnaest" to 15.0, "dvadeset" to 20.0, "trideset" to 30.0,
        "par" to 2.0, "pola" to 0.5, "pol" to 0.5,
    )

    /** Jedinica izgovora -> (jedinica kataloga, faktor). */
    private val jedinice = buildMap {
        for (w in listOf("kg", "kila", "kile", "kilu", "kilo", "kil", "kilogram", "kilograma", "kilograme")) put(w, "kg" to 1.0)
        for (w in listOf("g", "gr", "gram", "grama", "grame")) put(w, "kg" to 0.001)
        for (w in listOf("dag", "dkg", "deka", "deke", "dekagram", "dekagrama")) put(w, "kg" to 0.01)
        for (w in listOf("l", "lit", "litra", "litre", "litru", "litara", "litar", "liter")) put(w, "l" to 1.0)
        for (w in listOf("dl", "decilitar", "decilitra")) put(w, "l" to 0.1)
        for (w in listOf("ml", "mililitar", "mililitara")) put(w, "l" to 0.001)
        for (w in listOf("kom", "komad", "komada", "komadi", "kos", "komadic")) put(w, "kom" to 1.0)
    }
    private val pakiranja = setOf("pak", "paket", "paketa", "pakiranje", "pakiranja", "pakiranj", "kutija", "kutije", "boca", "boce", "bocu")
    private val popuna = setOf("i", "mi", "molim", "jos", "treba", "trebam", "kupi", "kupiti", "uzmi", "nesto", "malo")
    private val biljno = Regex("\\b(kokos\\w*|sojin\\w*|soja|bademov\\w*|zoben\\w*|rizino)\\b")
    private val razdjelnici = Regex("\\s*(?:,|;|\\n|\\bi\\b|\\bte\\b|\\bpa\\b)\\s*")

    /** "kruh, 2 mlijeka, deset jaja i banane" -> pojedinačni unosi. */
    fun razdvoji(tekst: String): List<String> =
        tekst.lowercase().split(razdjelnici).map { it.trim() }.filter { it.isNotEmpty() }

    private fun broj(w: String): Double? =
        brojevi[w] ?: w.replace('d', '.').toDoubleOrNull()?.takeIf { w.first().isDigit() }

    fun razumi(tekst: String, k: Katalog): Stavka {
        val r = Tekst.rijeci(tekst).filter { it !in popuna }.toMutableList()
        // 1. Količina: broj (ili riječ broja) s jedinicom, sama jedinica ("kila sira") ili broj pakiranja.
        var mnozitelj: Double? = null
        var iznos: Double? = null
        var jedinica: String? = null
        val potroseno = BooleanArray(r.size)
        var i = 0
        while (i < r.size) {
            val b = broj(r[i])
            val sljedeca = r.getOrNull(i + 1)
            when {
                b != null && sljedeca != null && sljedeca in jedinice && iznos == null -> {
                    val (j, f) = jedinice.getValue(sljedeca)
                    iznos = b * f; jedinica = j; potroseno[i] = true; potroseno[i + 1] = true; i++
                }
                b != null && sljedeca != null && sljedeca in pakiranja && mnozitelj == null -> {
                    mnozitelj = b; potroseno[i] = true; potroseno[i + 1] = true; i++
                }
                b != null && mnozitelj == null && iznos == null -> { mnozitelj = b; potroseno[i] = true }
                r[i] in jedinice && iznos == null && r[i].length > 2 -> {
                    val (j, f) = jedinice.getValue(r[i]); iznos = f; jedinica = j; potroseno[i] = true
                }
                r[i] in pakiranja -> potroseno[i] = true
            }
            i++
        }
        val ostale = r.filterIndexed { j, _ -> !potroseno[j] }

        // 2. Vrsta (skupina): isti postupak kao skupine.js za upit.
        val pogoci = mutableListOf<Triple<Grupa, Int, Int>>() // grupa, pozicija, duljina
        for (pos in ostale.indices) for (g in k.grupe) for (alias in g.aliasi) {
            if (alias.isNotEmpty() && alias.indices.all { j -> ostale.getOrNull(pos + j)?.let { Tekst.odgovara(it, alias[j], k.nastavci) } == true })
                pogoci.add(Triple(g, pos, alias.size))
        }
        val granica = ostale.indexOfFirst { it in k.prijedlozi }
        val glave = pogoci.filter { granica < 0 || it.second < granica || (it.second == 0 && it.third > 1) }
            .sortedWith(compareBy<Triple<Grupa, Int, Int>> { it.second }.thenByDescending { it.third })
        var glavni = glave.firstOrNull()
        if (glavni != null) {
            val posebno = k.zamjene[glavni.first.id]
            pogoci.firstOrNull { posebno != null && it.first.id in posebno }?.let { glavni = it }
            if (glavni!!.first.id == "mlijeko" && biljno.containsMatchIn(ostale.joinToString(" "))) {
                k.grupaPoId["biljno-mlijeko"]?.let { b -> glavni = Triple(b, glavni!!.second, glavni!!.third) }
            }
        }
        val grupa = glavni?.first
        val izostavi = mutableSetOf<Int>()
        glavni?.let { g ->
            val najdulji = pogoci.filter { it.first.id == g.first.id }.maxByOrNull { it.third } ?: g
            for (j in 0 until najdulji.third) izostavi.add(najdulji.second + j)
        }
        val dodatno = ostale.filterIndexed { j, w -> j !in izostavi && w !in k.prijedlozi }.map { Tekst.korijen(it) }

        // 3. Količina u jedinici kataloga.
        val zadano = grupa?.zadano
        val kolicina: Kolicina?
        val zadana: Boolean
        when {
            iznos != null -> {
                kolicina = Kolicina(iznos!! * (mnozitelj ?: 1.0), k.jedinice.indexOf(jedinica)); zadana = false
            }
            mnozitelj != null && zadano != null && k.jedinice.getOrNull(zadano.jedinica) == "kom" -> {
                kolicina = Kolicina(mnozitelj!!, zadano.jedinica); zadana = false
            }
            mnozitelj != null && zadano != null -> {
                kolicina = Kolicina(zadano.iznos * mnozitelj!!, zadano.jedinica); zadana = false
            }
            else -> { kolicina = zadano; zadana = true }
        }
        return Stavka(tekst.trim(), grupa, dodatno, kolicina, zadana)
    }

    /** Ista stavka dvaput se spaja: zbrajaju se količine. */
    fun spoji(stavke: List<Stavka>): List<Stavka> {
        val izlaz = LinkedHashMap<String, Stavka>()
        for (s in stavke) {
            val postojeca = izlaz[s.kljuc]
            izlaz[s.kljuc] = if (postojeca?.kolicina != null && s.kolicina != null && s.grupa != null)
                postojeca.copy(kolicina = postojeca.kolicina.copy(iznos = postojeca.kolicina.iznos + s.kolicina.iznos), zadanaKolicina = false)
            else postojeca ?: s
        }
        return izlaz.values.toList()
    }
}
