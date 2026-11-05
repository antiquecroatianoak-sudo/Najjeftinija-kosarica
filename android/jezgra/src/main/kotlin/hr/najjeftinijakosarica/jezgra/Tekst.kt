package hr.najjeftinijakosarica.jezgra

import java.text.Normalizer

/** Ista normalizacija kao site/skupine.js, da aplikacija i cjenik jednako čitaju riječi. */
object Tekst {
    private val kvacice = Regex("\\p{Mn}+")
    private val neSlovo = Regex("[^a-z0-9]+")
    private val samoglasniciNaKraju = Regex("[aeiou]+$")
    // "1,5 l" -> "1d5 l": decimalni zarez preživi normalizaciju kao jedna riječ.
    private val decimalni = Regex("(\\d)[,.](\\d)")

    fun normaliziraj(s: String): String {
        val malo = s.lowercase().replace("đ", "d")
        val bez = kvacice.replace(Normalizer.normalize(malo, Normalizer.Form.NFD), "")
        return neSlovo.replace(bez, " ").trim()
    }

    fun rijeci(s: String): List<String> =
        normaliziraj(decimalni.replace(s, "$1d$2")).split(" ").filter { it.isNotEmpty() }

    fun korijen(s: String): String {
        val k = if (s.length >= 4) samoglasniciNaKraju.replace(s, "") else s
        return if (k.length < 3) s else k
    }

    fun odgovara(rijec: String, korijen: String, nastavci: Set<String>): Boolean =
        rijec.startsWith(korijen) && rijec.substring(korijen.length) in nastavci

    /** Hrvatski zapis iznosa: 1234,5 -> "1.234,50 €". */
    fun eura(centi: Long): String {
        val apsolutno = kotlin.math.abs(centi)
        val cijeli = (apsolutno / 100).toString().reversed().chunked(3).joinToString(".").reversed()
        val ostatak = (apsolutno % 100).toString().padStart(2, '0')
        return (if (centi < 0) "-" else "") + "$cijeli,$ostatak €"
    }

    /** Količina za prikaz: 0,5 kg -> "500 g", 1,5 l -> "1,5 l", 10 kom -> "10 kom". */
    fun kolicina(iznos: Double, jedinica: String): String {
        fun broj(x: Double): String {
            val zaokruzeno = Math.round(x * 1000) / 1000.0
            return if (zaokruzeno == Math.floor(zaokruzeno)) zaokruzeno.toLong().toString()
            else zaokruzeno.toString().trimEnd('0').replace('.', ',')
        }
        return when {
            jedinica == "kg" && iznos < 1 -> "${broj(iznos * 1000)} g"
            jedinica == "l" && iznos < 1 -> "${broj(iznos * 1000)} ml"
            else -> "${broj(iznos)} $jedinica"
        }
    }
}
