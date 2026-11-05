package hr.najjeftinijakosarica.app

import android.content.Context
import hr.najjeftinijakosarica.jezgra.Katalog
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.GZIPInputStream

/**
 * Katalog cijena: zadnji spremljeni (ili ugrađeni u aplikaciju), a zatim provjera novog na internetu.
 * Lokacija korisnika se nikamo ne šalje; preuzima se samo zajednički katalog.
 */
class Podaci(private val ctx: Context) {
    private val spremljeni = File(ctx.filesDir, "katalog.json.gz")

    private fun procitaj(bajtovi: ByteArray): Katalog =
        Katalog.izJsona(GZIPInputStream(bajtovi.inputStream()).bufferedReader(Charsets.UTF_8).readText())

    /** Zadnje valjane cijene: spremljene, a ako su oštećene ili ih nema, one ugrađene u aplikaciju. */
    fun ucitajLokalno(): Katalog {
        if (spremljeni.exists()) {
            runCatching { return procitaj(spremljeni.readBytes()) }
            spremljeni.delete()
        }
        return procitaj(ctx.assets.open("katalog.json.gz").use { it.readBytes() })
    }

    /** Novi katalog s interneta, samo ako nije stariji od trenutnog (zaštita od starijeg cjenika). */
    fun osvjezi(trenutni: Katalog?): Katalog? {
        val veza = URL(BuildConfig.KATALOG_URL).openConnection() as HttpURLConnection
        veza.connectTimeout = 15_000
        veza.readTimeout = 60_000
        veza.instanceFollowRedirects = true
        try {
            if (veza.responseCode != 200) return null
            val bajtovi = veza.inputStream.use { it.readBytes() }
            val novi = procitaj(bajtovi)
            if (trenutni != null && novi.datum < trenutni.datum) return null
            if (trenutni != null && novi.datum == trenutni.datum && novi.izdanje == trenutni.izdanje) return null
            val privremeni = File(ctx.filesDir, "katalog.json.gz.tmp")
            privremeni.writeBytes(bajtovi)
            privremeni.renameTo(spremljeni)
            return novi
        } finally {
            veza.disconnect()
        }
    }
}
